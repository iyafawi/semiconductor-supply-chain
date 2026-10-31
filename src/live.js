import {useEffect,useState} from 'react';
export const API=(import.meta.env.VITE_API_URL||'http://127.0.0.1:8000').replace(/\/$/,'');
export const REFRESH=Math.max(30,Math.min(60,Number(import.meta.env.VITE_REFRESH_SECONDS)||45));
export function useLiveData(){
  const [data,setData]=useState(null),[live,setLive]=useState({status:'connecting',error:'',sources:[],articles:[],lastUpdated:null,regions:[]});
  useEffect(()=>{
    let stopped=false,timer,controller;
    async function poll(){
      controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),15000);
      try{
        const paths=['/api/network','/api/events/active','/api/alerts','/api/ingestion/status','/api/news/latest','/api/health'];
        const responses=await Promise.all(paths.map(async path=>{const r=await fetch(API+path,{signal:controller.signal,cache:'no-store'});if(!r.ok)throw new Error('Local API or SQL Server unavailable ('+r.status+')');return r.json();}));
        if(stopped)return;
        const [network,eventData,alerts,ingestion,news]=responses;
        const online=['online','degraded'].includes(ingestion.status);
        const riskById=new Map(alerts.suppliers.map(s=>[s.id,s]));
        const suppliers=network.suppliers.map(s=>({...s,...riskById.get(s.id),risk:online?riskById.get(s.id)?.risk||'Unknown':'Unknown',live_available:online}));
        const events=eventData.events.map(e=>({...e,time:e.published_at,category:e.event_type.replaceAll('_',' ')}));
        setData({...network,suppliers,events,live_status:ingestion.status});
        setLive({status:ingestion.status,error:online?'':'Worker has no recent successful feed refresh. Start the ingestion worker.',sources:ingestion.sources,articles:news.articles,lastUpdated:alerts.as_of,regions:alerts.regions,lastRun:ingestion.last_run,totalArticles:ingestion.total_articles,pendingArticles:ingestion.pending_articles,weights:alerts.weights,pollSeconds:ingestion.poll_seconds});
      }catch(error){
        if(stopped)return;
        setLive(previous=>({...previous,status:'offline',error:error.name==='AbortError'?'Local API timed out. Check the backend and SQL Server.':error.message,articles:[]}));
        setData(previous=>previous?{...previous,live_status:'offline',events:[],suppliers:previous.suppliers.map(s=>({...s,risk:'Unknown',priority:'Unavailable',events:[],current_live_risk:null,live_available:false}))}:null);
      }finally{
        clearTimeout(timeout);if(!stopped)timer=setTimeout(poll,REFRESH*1000);
      }
    }
    poll();return()=>{stopped=true;clearTimeout(timer);controller?.abort();};
  },[]);
  return {data,live};
}
