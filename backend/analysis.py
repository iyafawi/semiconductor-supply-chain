"""Deterministic supplier-component analysis; no supplier-to-supplier edges."""
def analyze(data):
    components = []
    for c in data['components']:
        ids = [r['supplier'] for r in data['relationships'] if r['component'] == c['id']]
        n = len(ids)
        components.append({**c, 'suppliers': ids, 'total': n, 'alternatives': max(0, n - 1),
                           'vulnerability': 'Critical' if n <= 1 else 'High' if n == 2 else 'Moderate' if n <= 4 else 'Low'})
    suppliers = []
    for s in data['suppliers']:
        cs = [c for c in components if s['id'] in c['suppliers']]
        events = s.get('events', [e for e in data.get('events',[]) if e.get('supplier') == s['id'] or e.get('country') == s['country']])
        risk = s.get('risk','Unknown')
        suppliers.append({**s, 'components': cs, 'raw': sum(c['importance']/c['total'] for c in cs),
                          'lowest': min((c['alternatives'] for c in cs), default=0), 'events': events, 'risk': risk})
    peak = max((s['raw'] for s in suppliers), default=1) or 1
    for s in suppliers:
        s['criticality'] = int(s['raw']/peak*100 + .5)
        s['priority'] = 'Unavailable' if s['risk']=='Unknown' else 'Critical alert' if s['risk'] == 'High' and s['lowest'] <= 1 else 'Investigate' if s['risk'] in ['High','Moderate'] and s['lowest'] <= 2 else 'Monitor'
    return {'suppliers': suppliers, 'components': components}

def simulate(components, removed):
    return [{**c, 'before': c['total'], 'remaining': len(set(c['suppliers']) - set(removed))}
            for c in components if set(c['suppliers']) & set(removed)]
