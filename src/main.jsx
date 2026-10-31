import React, { useState, useEffect, useMemo } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Globe2,
  Network,
  ShieldAlert,
  Layers3,
  FlaskConical,
  ChevronDown,
  ArrowUpRight,
  Search,
  Download,
  SlidersHorizontal,
  RotateCcw,
  Plus,
  Minus,
  X,
  ArrowRight,
  Activity,
  Settings2,
  Info,
  Radio,
  Check,
} from 'lucide-react';
import { geoNaturalEarth1, geoPath } from 'd3-geo';
import { analyze, simulate } from './model';
import { useLiveData } from './live';
import {
  ConnectionStatus,
  EventFeed,
  LiveEventsPanel,
  LiveSources,
  SupplierEvents,
  statusText,
  formatTime,
} from './LivePanels';
import './style.css';
const color = {
  High: '#fb7779',
  Moderate: '#e4b265',
  Low: '#61b6a6',
  Unknown: '#81909f',
};
function App() {
  const { data, live } = useLiveData();
  const [world, setWorld] = useState(null),
    [view, setView] = useState('Overview'),
    [country, setCountry] = useState('All countries'),
    [component, setComponent] = useState('All components'),
    [category, setCategory] = useState('All categories'),
    [risk, setRisk] = useState('All risk levels'),
    [critical, setCritical] = useState('All criticality'),
    [query, setQuery] = useState(''),
    [selected, setSelected] = useState(null),
    [focusedSupplier, setFocusedSupplier] = useState(null),
    [scenario, setScenario] = useState('s0'),
    [result, setResult] = useState(null),
    [sort, setSort] = useState('priority'),
    [zoom, setZoom] = useState(1),
    [networkComponent, setNetworkComponent] = useState(0),
    [method, setMethod] = useState(false),
    [error, setError] = useState('');
  useEffect(() => {
    fetch('/world.json')
      .then((r) => r.json())
      .then(setWorld)
      .catch(() => setError('Map geography could not load.'));
  }, []);
  const model = useMemo(() => (data ? analyze(data) : null), [data]);
  if (!model || !world)
    return (
      <div className="local-offline">
        <Layers3 size={35} />
        <h1>Silicon Watch · Private local workspace</h1>
        <ConnectionStatus live={live} />
        <p>
          {error ||
            'The dashboard loads its suppliers, components, news and risk from the local FastAPI service and SQL Server.'}
        </p>
        <p>
          Run start-local.ps1 in the project folder. This screen retries
          automatically every 45 seconds.
        </p>
        <a href="http://127.0.0.1:8000/docs">Local API documentation</a>
      </div>
    );
  const { suppliers, components } = model;
  const filtered = suppliers.filter(
    (s) =>
      (country === 'All countries' || s.country === country) &&
      (category === 'All categories' || s.category === category) &&
      (risk === 'All risk levels' || s.risk === risk) &&
      (critical === 'All criticality' ||
        (critical === 'High (≥60)'
          ? s.criticality >= 60
          : s.criticality < 60)) &&
      (component === 'All components' ||
        s.components.some((c) => c.name === component)) &&
      s.name.toLowerCase().includes(query.toLowerCase()),
  );
  const ranking = [...suppliers]
    .sort((a, b) => b.criticality - a.criticality)
    .filter((s) => s.lowest <= 1)
    .slice(0, 5);
  const rankPriority = (s) =>
    s.priority === 'Critical alert'
      ? 3
      : s.priority === 'Investigate'
        ? 2
        : s.priority === 'Unavailable'
          ? 0
          : 1;
  const rows = [...filtered].sort((a, b) =>
    sort === 'criticality'
      ? b.criticality - a.criticality
      : sort === 'risk'
        ? { High: 3, Moderate: 2, Low: 1, Unknown: 0 }[b.risk] -
          { High: 3, Moderate: 2, Low: 1 }[a.risk]
        : sort === 'redundancy'
          ? a.lowest - b.lowest
          : rankPriority(b) - rankPriority(a) || b.criticality - a.criticality,
  );
  const supplier =
    selected !== null ? suppliers.find((s) => s.id === selected) : null;
  const projection = geoNaturalEarth1().fitExtent(
    [
      [40, 40],
      [990, 450],
    ],
    world,
  );
  const path = geoPath(projection);
  const alertCount = suppliers.filter(
    (s) => s.priority === 'Critical alert',
  ).length;
  function inspect(id) {
    setSelected(id);
    setFocusedSupplier(id);
  }
  function run(id = scenario) {
    const sc = data.scenarios.find((s) => s.id === id);
    setScenario(id);
    setResult({
      name: sc.name,
      removed: sc.suppliers,
      components: simulate(components, sc.suppliers),
    });
    setView('Simulations');
    setSelected(null);
  }
  function reset() {
    setCountry('All countries');
    setComponent('All components');
    setCategory('All categories');
    setRisk('All risk levels');
    setCritical('All criticality');
    setQuery('');
  }
  function exportData() {
    const text =
      'Supplier,Country,Criticality,Current risk,Components,Lowest alternatives,Priority\n' +
      rows
        .map((s) =>
          [
            s.name,
            s.country,
            s.criticality,
            s.risk,
            s.components.length,
            s.lowest,
            s.priority,
          ].join(','),
        )
        .join('\n');
    const url = URL.createObjectURL(new Blob([text], { type: 'text/csv' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = 'silicon-watch-risk.csv';
    a.click();
    URL.revokeObjectURL(url);
  }
  const Select = ({ value, onChange, options }) => (
    <div className="select">
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => (
          <option key={o}>{o}</option>
        ))}
      </select>
      <ChevronDown size={12} />
    </div>
  );
  return (
    <div className="app">
      <aside className="sidebar">
        <a className="brand" href="#" onClick={() => setView('Overview')}>
          <div className="brand-icon">
            <Layers3 size={22} />
          </div>
          <span>
            SILICON<span className="brand-light">WATCH</span>
            <small>SUPPLY CHAIN INTELLIGENCE</small>
          </span>
        </a>
        <div className="workspace">
          <div className="avatar">SW</div>
          <div>
            Semiconductor portfolio<small>Local SQL Server workspace</small>
          </div>
          <ChevronDown size={13} />
        </div>
        <div className="nav-label">INTELLIGENCE</div>
        <nav>
          {[
            ['Overview', Globe2],
            ['Supply network', Network],
            ['Risk alerts', ShieldAlert],
            ['Components', Layers3],
            ['Simulations', FlaskConical],
          ].map(([label, Icon]) => (
            <button
              key={label}
              className={view === label ? 'nav active' : 'nav'}
              onClick={() => {
                setView(label);
                setSelected(null);
              }}
            >
              <Icon size={17} />
              {label}
              {label === 'Risk alerts' && (
                <span className="nav-count">{alertCount}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="demo-status">
            <span className="dot green" />
            Private local environment
            <small>48 suppliers · global coverage</small>
          </div>
          <button className="nav" onClick={() => setMethod(true)}>
            <Info size={16} />
            Model & methodology
          </button>
          <div className="profile">
            <div className="avatar">AN</div>
            <div>
              Analyst workspace<small>Live monitoring</small>
            </div>
            <Settings2 size={15} />
          </div>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div className="crumb">
            Workspace <span>/</span> Semiconductor intelligence
          </div>
          <div className="top-actions">
            <span className="env">
              <span className="dot green" /> PRIVATE LOCAL
            </span>
            <button
              className="icon-btn"
              title="Open model methodology"
              onClick={() => setMethod(true)}
            >
              <Info size={17} />
            </button>
            <div className="avatar small">AN</div>
          </div>
        </header>
        <div className="content">
          <div className="heading">
            <div>
              <div className="eyebrow">GLOBAL SUPPLY INTELLIGENCE</div>
              <h1>
                {view === 'Overview'
                  ? 'Supply-chain risk overview'
                  : view === 'Supply network'
                    ? 'Supplier–component network'
                    : view === 'Risk alerts'
                      ? 'Disruption risk intelligence'
                      : view === 'Components'
                        ? 'Component concentration'
                        : 'Disruption scenario lab'}
              </h1>
              <p>Understand your dependencies. Anticipate your exposure.</p>
            </div>
            <div className="heading-buttons">
              <button className="button" onClick={exportData}>
                <Download size={15} />
                Export report
              </button>
              <button className="button primary" onClick={() => run()}>
                <FlaskConical size={15} />
                Simulate disruption
              </button>
            </div>
          </div>
          <ConnectionStatus live={live} />
          <div className="demo-banner">
            <Info size={13} />
            <span>
              Real external news and events · Synthetic sourcing relationships
              and illustrative locations · No public deployment
            </span>
            <button onClick={() => setMethod(true)}>
              Methodology <ArrowUpRight size={12} />
            </button>
          </div>
          <div className="kpis">
            {[
              [
                suppliers.length,
                'Suppliers tracked',
                'Across ' +
                  new Set(suppliers.map((s) => s.country)).size +
                  ' countries',
                Globe2,
                '',
              ],
              [
                data.relationships.length,
                'Supply relationships',
                '32 semiconductor inputs',
                Network,
                '',
              ],
              [
                ranking.length,
                'Critical suppliers',
                'Limited sourcing alternatives',
                Activity,
                'amber',
              ],
              [
                live.status === 'offline' ? '—' : alertCount,
                'Priority risk alerts',
                'High risk + limited redundancy',
                ShieldAlert,
                'red',
              ],
              [
                components.filter((c) => c.alternatives <= 1).length,
                'Vulnerable components',
                'With 0–1 alternative suppliers',
                Layers3,
                'amber',
              ],
            ].map(([n, label, sub, Icon, tone]) => (
              <div className={'kpi ' + tone} key={label}>
                <div className="kpi-label">
                  {label}
                  <Icon size={16} />
                </div>
                <strong>{n.toString().padStart(2, '0')}</strong>
                <small>{sub}</small>
              </div>
            ))}
          </div>
          <div className="filters">
            <SlidersHorizontal size={15} />
            <Select
              value={country}
              onChange={setCountry}
              options={[
                'All countries',
                ...new Set(suppliers.map((s) => s.country)),
              ]}
            />
            <Select
              value={component}
              onChange={setComponent}
              options={['All components', ...components.map((c) => c.name)]}
            />
            <Select
              value={category}
              onChange={setCategory}
              options={[
                'All categories',
                ...new Set(suppliers.map((s) => s.category)),
              ]}
            />
            <Select
              value={risk}
              onChange={setRisk}
              options={[
                'All risk levels',
                'High',
                'Moderate',
                'Low',
                'Unknown',
              ]}
            />
            <Select
              value={critical}
              onChange={setCritical}
              options={['All criticality', 'High (≥60)', 'Lower (<60)']}
            />
            <button className="reset" onClick={reset}>
              <RotateCcw size={12} />
              Reset
            </button>
            <span className="filter-count">
              {filtered.length} of {suppliers.length} suppliers
            </span>
          </div>
          {view === 'Overview' && (
            <>
              <div className="map-row">
                <section className="panel map-panel">
                  <div className="panel-header">
                    <div>
                      <h2>Global risk landscape</h2>
                      <p>Supplier exposure and regional disruption signals</p>
                    </div>
                    <span className="small-tag">
                      <span className="dot green" />
                      LIVE EVENT EXPOSURE
                    </span>
                  </div>
                  <div className="map-wrap">
                    <svg
                      className="world"
                      viewBox="0 0 1030 490"
                      role="img"
                      aria-label="Interactive global supplier risk map"
                    >
                      <defs>
                        <pattern
                          id="grid"
                          width="50"
                          height="50"
                          patternUnits="userSpaceOnUse"
                        >
                          <path
                            d="M 50 0 L 0 0 0 50"
                            fill="none"
                            stroke="#1a2631"
                            strokeWidth=".5"
                          />
                        </pattern>
                        <radialGradient id="halo">
                          <stop stopColor="#e16f62" stopOpacity=".13" />
                          <stop
                            offset="1"
                            stopColor="#e16f62"
                            stopOpacity="0"
                          />
                        </radialGradient>
                      </defs>
                      <rect width="1030" height="490" fill="url(#grid)" />
                      <g
                        transform={`translate(${515 - 515 * zoom},${245 - 245 * zoom}) scale(${zoom})`}
                      >
                        {world.features
                          .filter((f) => f.properties.ADMIN !== 'Antarctica')
                          .map((f, i) => (
                            <path
                              key={i}
                              d={path(f)}
                              fill={
                                [
                                  'Taiwan',
                                  'China',
                                  'Japan',
                                  'South Korea',
                                ].includes(f.properties.ADMIN)
                                  ? '#283d40'
                                  : '#202d39'
                              }
                              stroke="#3b4a57"
                              strokeWidth=".7"
                            />
                          ))}
                        {data.events
                          .filter((e) =>
                            e.matches?.some((m) => m.match_type === 'regional'),
                          )
                          .map((e) => {
                            const s = suppliers.find((s) =>
                              e.matches.some(
                                (m) =>
                                  m.supplier_id === s.id &&
                                  m.match_type === 'regional',
                              ),
                            );
                            if (!s) return null;
                            const [x, y] = projection([s.lon, s.lat]);
                            return (
                              <g key={e.id}>
                                <circle
                                  cx={x}
                                  cy={y}
                                  r={40}
                                  fill="url(#halo)"
                                />
                                <circle
                                  cx={x}
                                  cy={y}
                                  r={22}
                                  fill="none"
                                  stroke={
                                    e.severity >= 0.7
                                      ? color.High
                                      : color.Moderate
                                  }
                                  strokeOpacity=".5"
                                  strokeDasharray="3 4"
                                />
                              </g>
                            );
                          })}
                        {filtered.map((s, i) => {
                          let [x, y] = projection([s.lon, s.lat]);
                          x += ((i % 3) - 1) * 7;
                          y += ((i % 4) - 1) * 6;
                          return (
                            <g
                              key={s.id}
                              role="button"
                              tabIndex="0"
                              aria-label={s.name + ' ' + s.risk + ' risk'}
                              onClick={() => inspect(s.id)}
                              onKeyDown={(e) =>
                                e.key === 'Enter' && inspect(s.id)
                              }
                              className="marker"
                            >
                              <circle
                                cx={x}
                                cy={y}
                                r={6 + s.criticality / 16}
                                fill={color[s.risk]}
                                opacity=".12"
                              />
                              <circle
                                cx={x}
                                cy={y}
                                r={3 + s.criticality / 30}
                                fill={color[s.risk]}
                                stroke="#0d171f"
                                strokeWidth="1.2"
                              />
                              <title>
                                {s.name} · Criticality {s.criticality} ·{' '}
                                {s.risk} risk
                              </title>
                            </g>
                          );
                        })}
                        {[
                          ['NORTH AMERICA', -110, 50],
                          ['EUROPE', 15, 57],
                          ['EAST ASIA', 113, 42],
                          ['SOUTH AMERICA', -65, -20],
                          ['AFRICA', 20, 8],
                          ['OCEANIA', 138, -32],
                        ].map(([label, lon, lat]) => {
                          const [x, y] = projection([lon, lat]);
                          return (
                            <text
                              key={label}
                              x={x}
                              y={y}
                              className="continent"
                              textAnchor="middle"
                            >
                              {label}
                            </text>
                          );
                        })}
                      </g>
                    </svg>
                    <div className="map-overlay">
                      <span className="dot red" /> East Asia exposure{' '}
                      <strong>
                        {
                          suppliers.filter((s) => s.region === 'East Asia')
                            .length
                        }{' '}
                        suppliers
                      </strong>
                    </div>
                    <div className="map-controls">
                      <button
                        title="Zoom in"
                        onClick={() => setZoom(Math.min(2.5, zoom + 0.25))}
                      >
                        <Plus size={16} />
                      </button>
                      <button
                        title="Zoom out"
                        onClick={() => setZoom(Math.max(1, zoom - 0.25))}
                      >
                        <Minus size={16} />
                      </button>
                      <button title="Reset map" onClick={() => setZoom(1)}>
                        <RotateCcw size={14} />
                      </button>
                    </div>
                    <div className="map-label">
                      Natural Earth · Headquarters / illustrative locations
                    </div>
                  </div>
                  <div className="map-legend">
                    {['High', 'Moderate', 'Low'].map((r) => (
                      <span key={r}>
                        <i style={{ background: color[r] }} />
                        {r} risk
                      </span>
                    ))}
                    <span className="legend-separator" />
                    <span>
                      <i className="ring" />
                      Regional event
                    </span>
                    <span className="marker-note">
                      Marker size = structural criticality
                    </span>
                  </div>
                </section>
                <EventFeed
                  events={data.events}
                  suppliers={suppliers}
                  onView={() => setView('Risk alerts')}
                />
              </div>
              <div className="bottom-row">
                <section className="panel priority-panel">
                  <div className="panel-header">
                    <div>
                      <h2>
                        Critical dependencies{' '}
                        <span className="number-tag">TOP 5</span>
                      </h2>
                      <p>
                        Highest criticality suppliers with limited alternatives
                      </p>
                    </div>
                    <button
                      className="text-button"
                      onClick={() => setView('Supply network')}
                    >
                      Explore network <ArrowUpRight size={13} />
                    </button>
                  </div>
                  {ranking.map((s, i) => (
                    <button
                      className="rank-row"
                      key={s.id}
                      onClick={() => inspect(s.id)}
                    >
                      <span className="rank">0{i + 1}</span>
                      <div className="company-icon">
                        {s.name.slice(0, 2).toUpperCase()}
                      </div>
                      <div className="rank-name">
                        {s.name}
                        <small>
                          {s.country} · {s.category}
                        </small>
                      </div>
                      <div className="rank-score">
                        <strong>{s.criticality}</strong>
                        <div className="bar">
                          <span style={{ width: s.criticality + '%' }} />
                        </div>
                      </div>
                      <span className={'risk-dot ' + s.risk.toLowerCase()}>
                        {s.risk}
                      </span>
                      <span className="alternative">{s.lowest} alt.</span>
                      <ArrowUpRight size={14} />
                    </button>
                  ))}
                </section>
                <section className="panel exposure">
                  <div className="panel-header">
                    <div>
                      <h2>Sourcing resilience</h2>
                      <p>Component supplier coverage</p>
                    </div>
                    <Layers3 size={17} className="muted" />
                  </div>
                  <div className="resilience">
                    <div
                      className="donut"
                      style={{
                        background: `conic-gradient(#e77c7c 0deg ${(components.filter((c) => c.total === 1).length / 32) * 360}deg,#d5aa6d 0deg ${(components.filter((c) => c.total <= 2).length / 32) * 360}deg,#55a899 0deg)`,
                      }}
                    >
                      <div>
                        <strong>{components.length}</strong>
                        <small>COMPONENTS</small>
                      </div>
                    </div>
                    <div className="coverage-list">
                      {[
                        [
                          'Single source',
                          components.filter((c) => c.total === 1).length,
                          '#e77c7c',
                        ],
                        [
                          'Limited alternatives',
                          components.filter((c) => c.total === 2).length,
                          '#d5aa6d',
                        ],
                        [
                          'Diversified sourcing',
                          components.filter((c) => c.total > 2).length,
                          '#55a899',
                        ],
                      ].map(([label, n, c]) => (
                        <div key={label}>
                          <i style={{ background: c }} />
                          <span>{label}</span>
                          <strong>{n}</strong>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="insight">
                    <ShieldAlert size={16} />
                    <span>
                      <strong>
                        {components.filter((c) => c.total === 1).length}{' '}
                        components have no backup supplier.
                      </strong>
                      <br />
                      Prioritize alternative sourcing for critical inputs.
                    </span>
                  </div>
                  <button
                    className="text-button"
                    onClick={() => setView('Components')}
                  >
                    Review component vulnerabilities <ArrowRight size={13} />
                  </button>
                </section>
              </div>
            </>
          )}
          {view === 'Supply network' && (
            <section className="panel">
              <div className="panel-header">
                <div>
                  <h2>Concentration explorer</h2>
                  <p>
                    Click a component to reveal its suppliers. Click a supplier
                    for every input it supports.
                  </p>
                </div>
                <Select
                  value={components[networkComponent].name}
                  onChange={(v) => {
                    setNetworkComponent(
                      components.find((c) => c.name === v).id,
                    );
                    setSelected(null);
                    setFocusedSupplier(null);
                  }}
                  options={components.map((c) => c.name)}
                />
              </div>
              <div className="network-layout">
                <div className="component-list">
                  {components.map((c) => (
                    <button
                      key={c.id}
                      className={networkComponent === c.id ? 'chosen' : ''}
                      onClick={() => {
                        setNetworkComponent(c.id);
                        setSelected(null);
                        setFocusedSupplier(null);
                      }}
                    >
                      <span>{c.name}</span>
                      <span
                        className={'badge ' + (c.total <= 2 ? 'high' : 'low')}
                      >
                        {c.total} suppliers
                      </span>
                    </button>
                  ))}
                </div>
                <div className="network-canvas">
                  <svg viewBox="0 0 720 520">
                    <text x="40" y="25" className="network-label">
                      SUPPLIERS
                    </text>
                    <text x="510" y="25" className="network-label">
                      COMPONENTS
                    </text>
                    {(() => {
                      const activeSupplier = suppliers.find(
                        (s) => s.id === focusedSupplier,
                      );
                      const cs = activeSupplier
                        ? activeSupplier.components
                        : [components[networkComponent]];
                      const ss = activeSupplier
                        ? [activeSupplier]
                        : suppliers.filter((s) =>
                            components[networkComponent].suppliers.includes(
                              s.id,
                            ),
                          );
                      return (
                        <>
                          {ss.map((s, i) =>
                            cs
                              .filter((c) => c.suppliers.includes(s.id))
                              .map((c, j) => (
                                <path
                                  key={s.id + '-' + c.id}
                                  d={`M 230 ${55 + ((i + 0.5) * 420) / ss.length} C 350 ${55 + ((i + 0.5) * 420) / ss.length}, 390 ${55 + ((j + 0.5) * 420) / cs.length}, 480 ${55 + ((j + 0.5) * 420) / cs.length}`}
                                  stroke="#4a877f"
                                  strokeWidth="1.5"
                                  fill="none"
                                />
                              )),
                          )}
                          {ss.map((s, i) => (
                            <g
                              key={s.id}
                              tabIndex="0"
                              role="button"
                              onClick={() => inspect(s.id)}
                              onKeyDown={(e) =>
                                e.key === 'Enter' && inspect(s.id)
                              }
                            >
                              <rect
                                x="25"
                                y={40 + ((i + 0.5) * 420) / ss.length}
                                width="205"
                                height="30"
                                rx="5"
                                fill="#24333d"
                              />
                              <circle
                                cx="40"
                                cy={55 + ((i + 0.5) * 420) / ss.length}
                                r="4"
                                fill={color[s.risk]}
                              />
                              <text
                                x="53"
                                y={59 + ((i + 0.5) * 420) / ss.length}
                                fill="#dce6ec"
                                fontSize="11"
                              >
                                {s.name}
                              </text>
                            </g>
                          ))}
                          {cs.map((c, j) => (
                            <g
                              key={c.id}
                              role="button"
                              tabIndex="0"
                              onClick={() => {
                                setNetworkComponent(c.id);
                                setSelected(null);
                                setFocusedSupplier(null);
                              }}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                  setNetworkComponent(c.id);
                                  setSelected(null);
                                  setFocusedSupplier(null);
                                }
                              }}
                            >
                              <rect
                                x="480"
                                y={40 + ((j + 0.5) * 420) / cs.length}
                                width="215"
                                height="30"
                                rx="5"
                                fill={c.total <= 2 ? '#473337' : '#1c3a37'}
                              />
                              <text
                                x="492"
                                y={59 + ((j + 0.5) * 420) / cs.length}
                                fill="#e5e8e8"
                                fontSize="11"
                              >
                                {c.name} · {c.alternatives} alt.
                              </text>
                            </g>
                          ))}
                        </>
                      );
                    })()}
                  </svg>
                  <div className="network-note">
                    Edges represent “supplies component” relationships. All
                    sourcing links are synthetic.
                  </div>
                </div>
              </div>
            </section>
          )}
          {view === 'Risk alerts' && (
            <LiveEventsPanel
              data={data}
              live={live}
              country={country}
              filtered={filtered}
              onSelect={inspect}
            />
          )}
          {view === 'Components' && (
            <section className="panel">
              <div className="panel-header">
                <div>
                  <h2>Redundancy by component</h2>
                  <p>
                    Alternative count = total supplier count − 1. Importance is
                    scored from 1 to 10.
                  </p>
                </div>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Component</th>
                      <th>Importance</th>
                      <th>Total suppliers</th>
                      <th>Alternatives</th>
                      <th>Concentration</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {[...components]
                      .filter(
                        (c) =>
                          component === 'All components' ||
                          c.name === component,
                      )
                      .sort(
                        (a, b) =>
                          a.total - b.total || b.importance - a.importance,
                      )
                      .map((c) => (
                        <tr key={c.id}>
                          <td>{c.name}</td>
                          <td>{c.importance} / 10</td>
                          <td>{c.total}</td>
                          <td>{c.alternatives}</td>
                          <td>
                            <span
                              className={
                                'badge ' +
                                (c.total <= 2
                                  ? 'high'
                                  : c.total <= 4
                                    ? 'moderate'
                                    : 'low')
                              }
                            >
                              {c.vulnerability}
                            </span>
                          </td>
                          <td>
                            <button
                              className="text-button"
                              onClick={() => {
                                setNetworkComponent(c.id);
                                setSelected(null);
                                setFocusedSupplier(null);
                                setView('Supply network');
                              }}
                            >
                              View suppliers <ArrowUpRight size={12} />
                            </button>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
          {view === 'Simulations' && (
            <section className="panel simulation">
              <div className="panel-header">
                <div>
                  <h2>Test a disruption</h2>
                  <p>
                    Remove a supplier or an entire region, then recalculate
                    component coverage.
                  </p>
                </div>
                <span className="small-tag">
                  {data.scenarios.length} PRESET SCENARIOS
                </span>
              </div>
              <div className="scenario-form">
                <select
                  value={scenario}
                  onChange={(e) => {
                    setScenario(e.target.value);
                    setResult(null);
                  }}
                >
                  {data.scenarios.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
                <button className="button primary" onClick={() => run()}>
                  <FlaskConical size={15} />
                  Run simulation
                </button>
                <button className="button" onClick={() => setResult(null)}>
                  <RotateCcw size={14} />
                  Clear
                </button>
              </div>
              {result ? (
                <>
                  <div className="simulation-title">
                    <span className="dot red" />
                    <strong>{result.name}</strong>
                    <span>Temporary scenario · Baseline data unchanged</span>
                  </div>
                  <div className="simulation-stats">
                    {[
                      [result.removed.length, 'Suppliers unavailable'],
                      [result.components.length, 'Components affected'],
                      [
                        result.components.filter((c) => c.remaining === 0)
                          .length,
                        'Lose all coverage',
                      ],
                      [
                        result.components.filter((c) => c.remaining === 1)
                          .length,
                        'Only one supplier remains',
                      ],
                    ].map(([n, label]) => (
                      <div key={label}>
                        <strong>{n}</strong>
                        <small>{label}</small>
                      </div>
                    ))}
                  </div>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Affected component</th>
                          <th>Before</th>
                          <th>Remaining suppliers</th>
                          <th>Remaining alternatives</th>
                          <th>Impact</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.components
                          .sort((a, b) => a.remaining - b.remaining)
                          .map((c) => (
                            <tr key={c.id}>
                              <td>{c.name}</td>
                              <td>{c.before}</td>
                              <td>{c.remaining}</td>
                              <td>
                                {c.remaining === 0 ? 'None' : c.remaining - 1}
                              </td>
                              <td>
                                <span
                                  className={
                                    'badge ' +
                                    (c.remaining === 0
                                      ? 'high'
                                      : c.remaining === 1
                                        ? 'moderate'
                                        : 'low')
                                  }
                                >
                                  {c.remaining === 0
                                    ? 'Coverage lost'
                                    : c.remaining === 1
                                      ? 'Single source'
                                      : 'Coverage retained'}
                                </span>
                              </td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : (
                <div className="simulation-empty">
                  <FlaskConical size={35} />
                  <h3>What happens if a supplier goes offline?</h3>
                  <p>
                    Choose from 48 supplier outages and 6 regional disruption
                    scenarios.
                  </p>
                </div>
              )}
            </section>
          )}
          {view !== 'Components' && (
            <section className="panel table-panel">
              <div className="panel-header">
                <div>
                  <h2>Supplier risk & vulnerability</h2>
                  <p>
                    Structural importance, current exposure, and investigation
                    priority
                  </p>
                </div>
                <div className="table-tools">
                  <div className="search">
                    <Search size={13} />
                    <input
                      placeholder="Search suppliers…"
                      aria-label="Search suppliers"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                    />
                  </div>
                  <select
                    aria-label="Sort suppliers"
                    value={sort}
                    onChange={(e) => setSort(e.target.value)}
                  >
                    <option value="priority">Priority ↓</option>
                    <option value="criticality">Criticality ↓</option>
                    <option value="risk">Current risk ↓</option>
                    <option value="redundancy">Alternatives ↑</option>
                  </select>
                </div>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Supplier</th>
                      <th>
                        <button onClick={() => setSort('criticality')}>
                          Criticality ↓
                        </button>
                      </th>
                      <th>
                        <button onClick={() => setSort('risk')}>
                          Current risk ↓
                        </button>
                      </th>
                      <th>Components</th>
                      <th>
                        <button onClick={() => setSort('redundancy')}>
                          Lowest alternatives ↑
                        </button>
                      </th>
                      <th>
                        <button onClick={() => setSort('priority')}>
                          Priority ↓
                        </button>
                      </th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {rows.slice(0, view === 'Overview' ? 6 : 48).map((s) => (
                      <tr key={s.id} onClick={() => inspect(s.id)}>
                        <td>
                          <strong>{s.name}</strong>
                          <small>{s.country}</small>
                        </td>
                        <td>
                          <span className="table-score">
                            {s.criticality}
                            <span className="bar">
                              <span style={{ width: s.criticality + '%' }} />
                            </span>
                          </span>
                        </td>
                        <td>
                          <span className={'risk-dot ' + s.risk.toLowerCase()}>
                            {s.risk}
                          </span>
                        </td>
                        <td>{s.components.length}</td>
                        <td>
                          {s.lowest === 0 ? (
                            <span className="red-text">0 · Single source</span>
                          ) : (
                            s.lowest + ' alternatives'
                          )}
                        </td>
                        <td>
                          <span
                            className={
                              'badge ' +
                              (s.priority === 'Critical alert'
                                ? 'high'
                                : s.priority === 'Investigate'
                                  ? 'moderate'
                                  : 'low')
                            }
                          >
                            {s.priority}
                          </span>
                        </td>
                        <td>
                          <button
                            className="icon-btn"
                            aria-label={'Inspect ' + s.name}
                            onClick={() => inspect(s.id)}
                          >
                            <ArrowUpRight size={14} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!rows.length && (
                  <div className="empty">
                    No suppliers match these filters.{' '}
                    <button className="text-button" onClick={reset}>
                      Reset filters
                    </button>
                  </div>
                )}
              </div>
              <div className="table-footer">
                Showing {Math.min(rows.length, view === 'Overview' ? 6 : 48)} of{' '}
                {rows.length} suppliers{' '}
                <button
                  className="text-button"
                  onClick={() => setView('Supply network')}
                >
                  View supply network <ArrowRight size={13} />
                </button>
              </div>
            </section>
          )}
          <footer>
            {' '}
            SILICON WATCH <span>Supplier ↔ component intelligence</span>
            <span>Private local · Live external feeds · SQL Server</span>
          </footer>
        </div>
      </main>
      {supplier && (
        <>
          <div className="scrim" onClick={() => setSelected(null)} />
          <aside className="detail">
            <div className="detail-top">
              <span className="eyebrow">SUPPLIER INTELLIGENCE</span>
              <button
                className="icon-btn"
                aria-label="Close supplier detail"
                onClick={() => setSelected(null)}
              >
                <X size={19} />
              </button>
            </div>
            <div className="company-icon large">
              {supplier.name.slice(0, 2).toUpperCase()}
            </div>
            <h2>{supplier.name}</h2>
            <p>
              {supplier.country} · {supplier.category}
            </p>
            <div className="detail-metrics">
              <div>
                <small>Structural criticality</small>
                <strong>
                  {supplier.criticality}
                  <em>/100</em>
                </strong>
              </div>
              <div>
                <small>Current live risk</small>
                <strong style={{ color: color[supplier.risk] }}>
                  {supplier.risk}
                </strong>
                <small>
                  {supplier.current_live_risk != null
                    ? Math.round(supplier.current_live_risk * 100) +
                      '% · ' +
                      statusText(supplier.exposure_status)
                    : 'Monitoring offline'}
                </small>
              </div>
            </div>
            <span
              className={
                'badge ' +
                (supplier.priority === 'Critical alert' ? 'high' : 'low')
              }
            >
              {supplier.priority}
            </span>
            <h3>Component dependencies</h3>
            {supplier.components.map((c) => (
              <div className="dependency" key={c.id}>
                <div>
                  <strong>{c.name}</strong>
                  <small>
                    Importance {c.importance}/10 · {c.alternatives} alternatives
                  </small>
                </div>
                <span
                  className={'badge ' + (c.alternatives <= 1 ? 'high' : 'low')}
                >
                  {c.vulnerability}
                </span>
                <p>
                  {c.suppliers
                    .filter((id) => id !== supplier.id)
                    .map((id) => suppliers[id].name)
                    .join(', ') || 'No alternative supplier in this network.'}
                </p>
              </div>
            ))}
            <h3>Live events & evidence</h3>
            <SupplierEvents supplier={supplier} />
            <h3>Simulated supplier removal</h3>
            <p>
              {
                simulate(components, [supplier.id]).filter(
                  (c) => c.remaining === 0,
                ).length
              }{' '}
              components lose coverage;{' '}
              {
                simulate(components, [supplier.id]).filter(
                  (c) => c.remaining === 1,
                ).length
              }{' '}
              become single source.
            </p>
            <button
              className="button primary full"
              onClick={() => run('s' + supplier.id)}
            >
              <FlaskConical size={15} />
              Simulate this supplier
            </button>
          </aside>
        </>
      )}
      {method && (
        <div className="modal-backdrop" onClick={() => setMethod(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <button
              className="icon-btn close"
              aria-label="Close methodology"
              onClick={() => setMethod(false)}
            >
              <X size={20} />
            </button>
            <div className="eyebrow">TRANSPARENT BY DESIGN</div>
            <h2>Network informs priority.</h2>
            <p>
              The persisted network uses 48 real company names, 32 inputs, and
              synthetic supplier-component links. Relationships do not imply
              verified commercial capability, qualification, or sourcing.
            </p>
            <h3>Structural criticality</h3>
            <code>Raw score = Σ importance ÷ component supplier count</code>
            <p>
              Criticality = 100 × raw score / highest supplier raw score. Top
              five critical dependencies must also supply at least one component
              with 0–1 alternatives.
            </p>
            <h3>Current risk & priority</h3>
            <p>
              Live event risk = severity × source credibility × confidence ×
              recency, with a 48-hour half-life. Regional exposure receives a
              0.65 weight. Supplier risk is the maximum weighted active event,
              not a sum of duplicated stories. High live risk + 0–1 alternatives
              + criticality ≥50 → Critical alert. Elevated risk + up to 2
              alternatives → Investigate. Other combinations → Monitor. Offline
              monitoring is Unknown.
            </p>
            <h3>Private local architecture</h3>
            <p>
              External RSS, USGS and Federal Register feeds → local Python
              worker every 10 minutes → SQL Server article/event/risk tables →
              FastAPI → this dashboard every 45 seconds. There is no static news
              fallback. Reported interruption reflects explicit source wording;
              regional matches are potential exposure. All sourcing records and
              live evidence are persisted in SQL Server.
            </p>
            <button className="button primary" onClick={() => setMethod(false)}>
              <Check size={15} />
              Understood
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
createRoot(document.getElementById('root')).render(<App />);
