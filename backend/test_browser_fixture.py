"""Explicit isolated SQL Server fixture for verifying browser auto-refresh.
Never permitted against SiliconWatch or any unrecognized database name.
"""
import argparse,os,re
from settings import sources
from repository import connect,initialize,SqlRepository
from processing import utcnow,iso
from feeds import make_article
from worker import process_pending
def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','inject','cleanup']);p.add_argument('--database',required=True);args=p.parse_args()
    if not re.fullmatch(r'SiliconWatchTestBrowser_[0-9a-f]{12}',args.database):raise ValueError('Only an isolated generated browser-test database is permitted')
    base=os.environ['SQLSERVER_CONNECTION_STRING'];master=re.sub(r'(?i)Database\s*=\s*[^;]+','Database=master',base)
    if args.action=='cleanup':
        with connect(master,autocommit=True) as db:db.cursor().execute(f'ALTER DATABASE [{args.database}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE [{args.database}]')
        print('Isolated browser-test database removed.');return
    os.environ['SQLSERVER_CONNECTION_STRING']=re.sub(r'(?i)Database\s*=\s*[^;]+','Database='+args.database,base);os.environ['SQLSERVER_DATABASE']=args.database
    if args.action=='prepare':
        with connect(master,autocommit=True) as db:
            if db.cursor().execute('SELECT DB_ID(?)',args.database).fetchone()[0]:raise ValueError('Test database already exists; refusing to overwrite')
        initialize();repo=SqlRepository();now=iso(utcnow())
        for source in sources():repo.save_source_state({'id':source['id'],'name':source['name'],'url':source['url'],'last_attempt':now,'last_success':now,'status':'ok','retrieved_count':0,'new_count':0})
        print('Isolated browser fixture prepared with no articles.');return
    source={'id':'controlled-browser-test','name':'Controlled browser integration test','credibility':.95}
    now=utcnow();article=make_article(source,'CONTROLLED TEST: TSMC semiconductor factory shutdown halted wafer production','This article exists only in the isolated automated-test SQL Server database.','https://example.invalid/controlled-browser-test',now,now=now)
    repo=SqlRepository();repo.store_article(article);process_pending(repo)
    print('Controlled article persisted and processed in isolated SQL Server database.')
if __name__=='__main__':main()
