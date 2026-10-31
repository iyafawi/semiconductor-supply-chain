import unittest,json
from pathlib import Path
from datetime import timedelta
from analysis import analyze,simulate
from feeds import make_article
from processing import classify,utcnow,event_risk,find_cluster,merge_event,supplier_risks
SOURCE={'id':'controlled-test','name':'Controlled automated test','credibility':.9}
class AnalysisTests(unittest.TestCase):
    def setUp(self):self.network=json.loads((Path(__file__).parent/'seed/network.json').read_text(encoding='utf-8'));self.now=utcnow();self.model=analyze(self.network)
    def article(self,title,summary=''):
        return make_article(SOURCE,title,summary,'https://example.invalid/test',self.now,now=self.now)
    def test_single_source(self):
        c=next(c for c in self.model['components'] if c['total']==1);self.assertEqual(simulate(self.model['components'],c['suppliers'])[0]['remaining'],0)
    def test_normalized(self):self.assertEqual(max(s['criticality'] for s in self.model['suppliers']),100)
    def test_alias_and_confirmation(self):
        e,_=classify(self.article('Taiwan Semiconductor Manufacturing halted wafer production after factory fire'),self.network,self.now)
        self.assertEqual(e['matches'][0]['supplier_id'],0);self.assertEqual(e['status'],'confirmed_report')
    def test_negation(self):self.assertIsNone(classify(self.article('TSMC says semiconductor production unaffected by earthquake'),self.network,self.now)[0])
    def test_irrelevant(self):self.assertIsNone(classify(self.article('Sports championship in Japan'),self.network,self.now)[0])
    def test_region_is_potential(self):
        e,_=classify(self.article('Earthquake disrupts semiconductor manufacturing in Taiwan'),self.network,self.now)
        self.assertTrue(all(m['match_type']=='regional' and m['exposure_status']=='potential_exposure' for m in e['matches']))
    def test_uncertainty(self):
        e,_=classify(self.article('TSMC may face a semiconductor factory shutdown'),self.network,self.now)
        self.assertEqual(e['status'],'low_confidence');self.assertTrue(all(m['exposure_status']!='confirmed_report' for m in e['matches']))
    def test_decay_and_expiry(self):
        e,_=classify(self.article('TSMC halted semiconductor production after shutdown'),self.network,self.now)
        self.assertAlmostEqual(event_risk(e,self.now+timedelta(hours=48)),event_risk(e,self.now)/2,places=3);self.assertEqual(event_risk(e,self.now+timedelta(days=8)),0)
    def test_cluster_severity_not_summed(self):
        first,_=classify(self.article('TSMC semiconductor factory shutdown disrupts wafer production'),self.network,self.now)
        a=make_article({**SOURCE,'id':'other-test'},'TSMC semiconductor factory shutdown disrupts wafer production today','','https://example.invalid/two',self.now,now=self.now)
        second,_=classify(a,self.network,self.now);self.assertIsNotNone(find_cluster(second,[first]));merged=merge_event(first,second)
        self.assertEqual(merged['severity'],first['severity']);self.assertGreater(merged['confidence'],first['confidence']);self.assertEqual(len(merged['sources']),2)
    def test_geographic_radius(self):
        a=self.article('USGS earthquake');a['geo']={'lat':24.8,'lon':121,'magnitude':5,'radius_km':300}
        e,_=classify(a,self.network,self.now);self.assertEqual(e['status'],'potential_exposure');self.assertTrue(e['matches'])
        a['geo']['lat']=-70;self.assertIsNone(classify(a,self.network,self.now)[0])
    def test_risk_max_not_sum(self):
        e,_=classify(self.article('TSMC semiconductor shutdown halted production'),self.network,self.now)
        one=supplier_risks(self.network,[e],self.now)[0]['current_live_risk'];two=supplier_risks(self.network,[e,{**e,'id':'another'}],self.now)[0]['current_live_risk'];self.assertEqual(one,two)
if __name__=='__main__':unittest.main()
