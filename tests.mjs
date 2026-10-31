import assert from 'node:assert/strict';
import fs from 'node:fs';
import { analyze, simulate } from './src/model.js';
const data = JSON.parse(fs.readFileSync('backend/seed/network.json'));
const { suppliers, components } = analyze(data);
assert.ok(suppliers.length >= 40);
assert.ok(data.relationships.length >= 300);
assert.ok(components.length >= 20 && components.length <= 40);
assert.ok(data.scenarios.length >= 25);
assert.equal(
  new Set(data.relationships.map((r) => r.supplier + ':' + r.component)).size,
  data.relationships.length,
);
assert.equal(Math.max(...suppliers.map((s) => s.criticality)), 100);
const single = components.find((c) => c.total === 1);
assert.equal(
  simulate(components, single.suppliers).find((c) => c.id === single.id)
    .remaining,
  0,
);
const double = components.find((c) => c.total === 2);
assert.equal(
  simulate(components, [double.suppliers[0]]).find((c) => c.id === double.id)
    .remaining,
  1,
);
for (const sc of data.scenarios) {
  const affected = simulate(components, sc.suppliers);
  assert.ok(affected.every((c) => c.remaining >= 0 && c.remaining < c.before));
}
assert.equal(components.find((c) => c.id === single.id).total, 1);
assert.equal(simulate(components, []).length, 0);
console.log(
  'Dataset, uniqueness, criticality normalization, single-source loss, redundancy, 54 scenarios and baseline integrity passed.',
);
