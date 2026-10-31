"""Automatic local SQL Server ingestion. One worker owns a SQL application lock."""
import argparse, json, logging, signal, threading, time
from processing import classify, find_cluster, merge_event, iso, utcnow
from repository import SqlRepository,connect
from settings import sources,POLL_SECONDS
from feeds import fetch_source
log=logging.getLogger('siliconwatch.ingestion')

def process_pending(repo):
    network=repo.network();events=repo.events();processed=0
    for article in repo.pending_articles():
        try:
            event,reason=classify(article,network)
            if event:
                cluster=find_cluster(event,events)
                if cluster:
                    event=merge_event(cluster,event);events=[e for e in events if e['id']!=cluster['id']]
                repo.finish_article(article['id'],event,reason);events.append(event);processed+=1
            else:repo.finish_article(article['id'],None,reason)
            log.info('article_processed article=%s result=%s event=%s',article['id'][:12],reason,event['id'][:12] if event else '-')
        except Exception:
            log.exception('article_processing_failed article=%s; remains pending for retry',article['id'][:12])
    repo.update_risks(network,repo.events());return processed

def run_once(repo=None,fetcher=fetch_source):
    repo=repo or SqlRepository();start=iso(utcnow());states={s['id']:s for s in repo.source_states()};ok=failed=new_count=0
    for source in sources():
        old=states.get(source['id'],{});now=iso(utcnow());state={**old,'id':source['id'],'name':source['name'],'url':source['url'],'last_attempt':now}
        try:
            articles,headers=fetcher(source,old);new=sum(repo.store_article(a) for a in articles)
            state.update(headers);state.update(status='ok',last_success=now,last_error=None,retrieved_count=len(articles),new_count=new)
            ok+=1;new_count+=new;log.info('source_refresh_ok source=%s retrieved=%s new=%s',source['id'],len(articles),new)
        except Exception as exc:
            failed+=1;state.update(status='failed',last_error=type(exc).__name__,retrieved_count=0,new_count=0)
            log.error('source_refresh_failed source=%s error=%s; continuing other feeds',source['id'],type(exc).__name__)
        repo.save_source_state(state)
    processed=process_pending(repo);repo.save_run(start,iso(utcnow()),ok,failed,new_count,processed)
    return {'sources_ok':ok,'sources_failed':failed,'articles_new':new_count,'events_processed':processed}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true');parser.add_argument('--probe',action='store_true',help='Retrieve real sources without persistence; diagnostic only');args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s %(message)s')
    if args.probe:
        for source in sources():
            try:
                articles,_=fetch_source(source)
                print(json.dumps({'source':source['name'],'retrieved':len(articles),'latest':articles[0]['published_at'] if articles else None}))
            except Exception as exc:print(json.dumps({'source':source['name'],'error':type(exc).__name__}))
        return
    stop=threading.Event()
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.set())
    while not stop.is_set():
        try:
            # Session lock prevents concurrent workers, including across app restarts.
            with connect(autocommit=True) as lock:
                row=lock.cursor().execute("DECLARE @r INT; EXEC @r=sp_getapplock @Resource='SiliconWatchIngestion',@LockMode='Exclusive',@LockOwner='Session',@LockTimeout=0; SELECT @r;").fetchone()
                if not row or row[0]<0:raise RuntimeError('Another ingestion worker is already running')
                while not stop.is_set():
                    log.info('refresh_complete %s',json.dumps(run_once()))
                    if args.once:return
                    stop.wait(POLL_SECONDS)
        except Exception as exc:
            log.error('worker_unavailable error=%s; SQL Server required, no persistence fallback',type(exc).__name__)
            if args.once:raise
            stop.wait(30)
if __name__=='__main__':main()
