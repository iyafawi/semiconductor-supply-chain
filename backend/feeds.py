"""Real RSS, USGS GeoJSON and Federal Register retrieval; no browser collection."""
import calendar, hashlib, json, os
from datetime import datetime, timezone
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
import feedparser, httpx
from processing import clean, utcnow, iso

def canonical_url(url):
    parts=urlsplit(url)
    if parts.scheme not in ('https','http'):return ''
    query=[(k,v) for k,v in parse_qsl(parts.query) if not k.lower().startswith('utm_') and k not in ['fbclid','gclid']]
    return urlunsplit((parts.scheme,parts.netloc.lower(),parts.path,urlencode(query),''))
def make_article(source,title,description,url,published=None,external_id=None,geo=None,now=None):
    now=now or utcnow();url=canonical_url(url)
    identity=external_id or url or (clean(title).lower()+str(published))
    return {'id':hashlib.sha256((source['id']+':'+identity).encode()).hexdigest(),'title':clean(title),'description':clean(description)[:12000],
            'source':source['name'],'source_id':source['id'],'url':url,'published_at':iso(published or now),'retrieved_at':iso(now),
            'published_time_confidence':1 if published else .6,'credibility':source['credibility'],**({'geo':geo} if geo else {})}
def fetch_source(source,state=None):
    if source['kind'] == 'openai_search':
        from openai_news import fetch_openai_news
        return fetch_openai_news(source)
    state=state or {};headers={'User-Agent':'SiliconWatchLocal/2.0 (private semiconductor risk research)','Accept':'application/json, application/atom+xml, application/rss+xml, application/xml, text/xml'}
    if state.get('etag'):headers['If-None-Match']=state['etag']
    if state.get('last_modified'):headers['If-Modified-Since']=state['last_modified']
    # Optional API tokens are named in source config and read only from the environment.
    if source.get('api_key_env'):
        token=os.getenv(source['api_key_env'])
        if not token:raise RuntimeError('Required source API key is not configured')
        headers[source.get('api_key_header','Authorization')]=token
    if not source['url'].startswith('https://'):raise ValueError('Configured sources must use HTTPS')
    with httpx.Client(timeout=httpx.Timeout(30,connect=10),follow_redirects=True,transport=httpx.HTTPTransport(retries=2)) as client:
        response=client.get(source['url'],headers=headers)
    metadata={'etag':response.headers.get('etag',state.get('etag')),'last_modified':response.headers.get('last-modified',state.get('last_modified'))}
    if response.status_code==304:return [],metadata
    response.raise_for_status()
    if len(response.content)>10_000_000:raise ValueError('Feed exceeds 10 MB limit')
    now=utcnow();articles=[]
    if source['kind']=='rss':
        feed=feedparser.parse(response.content)
        if feed.bozo and not feed.entries:raise ValueError('Invalid RSS/Atom response')
        for e in feed.entries[:200]:
            date=e.get('published_parsed') or e.get('updated_parsed')
            published=datetime.fromtimestamp(calendar.timegm(date),timezone.utc) if date else None
            articles.append(make_article(source,e.get('title',''),e.get('summary',''),e.get('link',''),published,e.get('id'),now=now))
    elif source['kind']=='usgs':
        for feature in response.json()['features']:
            p=feature['properties'];lon,lat,depth=feature['geometry']['coordinates'];mag=p.get('mag') or 0
            if mag<source.get('minimum_magnitude',4.5):continue
            articles.append(make_article(source,p['title'],f"USGS reports a magnitude {mag} earthquake near {p.get('place','unknown location')}, depth {depth} km. This does not establish supplier damage.",p['url'],datetime.fromtimestamp(p['time']/1000,timezone.utc),feature['id'],{'external_id':feature['id'],'lon':lon,'lat':lat,'depth_km':depth,'magnitude':mag,'minimum_magnitude':source.get('minimum_magnitude',4.5),'radius_km':source.get('exposure_radius_km',300)},now))
    elif source['kind']=='federal_register':
        for d in response.json()['results']:
            date=datetime.fromisoformat(d['publication_date']).replace(tzinfo=timezone.utc)
            articles.append(make_article(source,d['title'],d.get('abstract') or '',d['html_url'],date,d['document_number'],now=now))
    else:raise ValueError('Unsupported source kind')
    return articles,metadata
