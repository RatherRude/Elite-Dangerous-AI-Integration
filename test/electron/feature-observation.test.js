import assert from 'node:assert/strict';
import test from 'node:test';
import { observeFeatureOperation } from '../../electron/feature-observation.js';

test('VR failure reports explicit metadata while preserving the original rejection', async () => {
  const events = [];
  const error = Object.assign(new Error('SENSITIVE_RUNTIME_PATH'), { code: 'vr_setup_required' });
  await assert.rejects(observeFeatureOperation(event => events.push(event), 'vr', 'initialize', async () => { throw error; }), value => value === error);
  assert.deepEqual(events, [{ type: 'internal_operation', component: 'vr', operation: 'initialize', status: 'error', error_kind: 'vr_setup_required' }]);
  assert.ok(!JSON.stringify(events).includes('SENSITIVE_'));
});
test('reporting failures do not alter successful or failed operations', async () => {
  const report = () => { throw new Error('export failed'); };
  assert.equal(await observeFeatureOperation(report, 'desktop_overlay', 'initialize', async () => 42), 42);
  const failure = new Error('original');
  await assert.rejects(observeFeatureOperation(report, 'vr', 'initialize', async () => { throw failure; }), error => error === failure);
});
