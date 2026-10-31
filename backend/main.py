"""Private local API. All application records come from SQL Server."""
import logging, os
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import pyodbc
from settings import public_weights, ALERT_CRITICALITY_THRESHOLD
from repository import SqlRepository, DatabaseUnavailable
from processing import supplier_risks, event_risk, iso, utcnow
from analysis import analyze, simulate
log=logging.getLogger('siliconwatch.api')
app=FastAPI(title='Silicon Watch · Local Live API',version='2.0',description='Live article evidence and supplier-component risk, persisted exclusively in SQL Server.')
app.add_middleware(CORSMiddleware,allow_origins=os.getenv('FRONTEND_ORIGINS','http://127.0.0.1:5173,http://localhost:5173').split(','),allow_methods=['GET','POST'],allow_headers=['Content-Type'])
@app.middleware('http')
async def no_cache(request:Request,call_next):
    response=await call_next(request);response.headers['Cache-Control']='no-store';return response
@app.exception_handler(DatabaseUnavailable)
async def unavailable(request,exc):
    return JSONResponse(status_code=503,content={'status':'offline','detail':str(exc),'database':'sqlserver','fallback':False})
@app.exception_handler(pyodbc.Error)
async def database_error(request,exc):
    log.error('sql_query_failed operation=%s error_type=%s',request.url.path,type(exc).__name__)
    return JSONResponse(status_code=503,content={'status':'offline','detail':'SQL Server schema/query unavailable. Initialize the database and check server logs.','fallback':False})
def repository():return SqlRepository()

def live_model(repo):
    data=repo.network();events=repo.events();status=repo.ingestion_status()
    risks={r['supplier_id']:r for r in supplier_risks(data,events)}
    usable=status['status'] in ['online','degraded']
    data['suppliers']=[{**s,**risks[s['id']],'risk':risks[s['id']]['risk'] if usable else 'Unknown','live_available':usable} for s in data['suppliers']]
    data['events']=[{**e,'event_risk':event_risk(e),'time':e['published_at']} for e in events]
    data['live_status']=status['status'];data['as_of']=iso(utcnow())
    model=analyze(data)
    for s in model['suppliers']:
        if not usable:s['priority']='Unavailable'
        elif s['risk']=='High' and s['lowest']<=1 and s['criticality']>=ALERT_CRITICALITY_THRESHOLD:s['priority']='Critical alert'
        elif s['risk'] in ['High','Moderate'] and s['lowest']<=2:s['priority']='Investigate'
        else:s['priority']='Monitor'
    return data,model,status

class Disruption(BaseModel):supplier_ids:list[int]=Field(min_length=1,max_length=100)
@app.get('/api/network')
def network(repo=Depends(repository)):return repo.network()
@app.get('/api/data')
def data(repo=Depends(repository)):return live_model(repo)[0]
@app.get('/api/analysis')
def analysis(repo=Depends(repository)):return live_model(repo)[1]
@app.get('/api/news/latest')
def news(limit:int=Query(50,ge=1,le=200),repo=Depends(repository)):return {'articles':repo.latest_news(limit),'as_of':iso(utcnow())}
@app.get('/api/events/active')
def events(repo=Depends(repository)):
    return {'events':[{**e,'event_risk':event_risk(e),'time':e['published_at']} for e in repo.events()],'as_of':iso(utcnow())}
@app.get('/api/events')
def legacy_events(repo=Depends(repository)):return events(repo)['events']
@app.get('/api/alerts')
def alerts(repo=Depends(repository)):
    _,model,status=live_model(repo)
    suppliers=[{**s,'lowest_alternatives':s['lowest'],'live_risk':s['current_live_risk']} for s in model['suppliers']]
    return {'suppliers':suppliers,'alerts':[s for s in suppliers if s['priority'] in ['Critical alert','Investigate']],
            'regions':repo.regional_rows(),'live_status':status['status'],'as_of':iso(utcnow()),'weights':public_weights()}
@app.get('/api/suppliers/{supplier_id}')
def supplier(supplier_id:int,repo=Depends(repository)):
    _,model,_=live_model(repo);result=next((s for s in model['suppliers'] if s['id']==supplier_id),None)
    if result is None:raise HTTPException(404,'Unknown supplier')
    return result
@app.get('/api/suppliers/{supplier_id}/risk')
def risk(supplier_id:int,repo=Depends(repository)):
    s=supplier(supplier_id,repo)
    return {k:s[k] for k in ['id','name','country','criticality','risk','current_live_risk','exposure_status','events','updated_at','priority']}
@app.get('/api/suppliers/{supplier_id}/risk/history')
def history(supplier_id:int,repo=Depends(repository)):
    supplier(supplier_id,repo);return {'supplier_id':supplier_id,'history':repo.history(supplier_id)}
@app.get('/api/regions/{region}/risk')
def region_risk(region:str,repo=Depends(repository)):
    rows=repo.regional_rows();r=next((r for r in rows if r['region'].lower()==region.lower()),None)
    if r is None:raise HTTPException(404,'Unknown region')
    network=repo.network();ids={s['id'] for s in network['suppliers'] if s['country'].lower()==region.lower()}
    return {**r,'events':[e for e in repo.events() if any(m['supplier_id'] in ids and m['match_type']=='regional' for m in e['matches'])]}
@app.get('/api/scenarios')
def scenarios(repo=Depends(repository)):return repo.network()['scenarios']
@app.post('/api/simulate')
def disruption(request:Disruption,repo=Depends(repository)):
    model=analyze(repo.network())
    if set(request.supplier_ids)-{s['id'] for s in model['suppliers']}:raise HTTPException(400,'Unknown supplier IDs')
    affected=simulate(model['components'],request.supplier_ids)
    return {'affected_components':affected,'zero_coverage':sum(c['remaining']==0 for c in affected),'single_source':sum(c['remaining']==1 for c in affected),'importance_lost':sum(c['importance'] for c in affected if c['remaining']==0)}
@app.get('/api/ingestion/status')
def ingestion(repo=Depends(repository)):return repo.ingestion_status()
@app.get('/api/health')
def health(repo=Depends(repository)):
    try:
        info=repo.health();state=repo.ingestion_status()
        return {**info,'status':state['status'],'worker_last_run':state['last_run'],'as_of':iso(utcnow())}
    except (DatabaseUnavailable,pyodbc.Error):
        return JSONResponse(status_code=503,content={'status':'offline','database':'sqlserver','database_connected':False,'fallback':False,'detail':'SQL Server is required. Check local installation and initialize the schema.'})
