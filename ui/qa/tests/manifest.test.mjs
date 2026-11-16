import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { qaFixtures, source, tests, validateManifest } from '../acceptance-contract.mjs';

describe('CHAT1 CAD acceptance manifest (not browser E2E)', () => {
  it('has unique numbered IDs and one fixture/action/invariant per case', () => {
    assert.deepEqual(validateManifest(), []);
    assert.equal(new Set(tests.map(t => t.id)).size, tests.length);
  });
  it('covers critical R2/R3/R4 scenarios', () => {
    assert.equal(tests.length, 12);
    for (const id of [
      'CAD-UX-R2-01','CAD-UX-R2-02','CAD-UX-R2-03','CAD-UX-R2-04',
      'CAD-UX-R2-05','CAD-UX-R3-01','CAD-UX-R3-02','CAD-UX-R3-03',
      'CAD-UX-R3-04','CAD-UX-R3-05','CAD-UX-R3-06','CAD-UX-R4-01',
    ]) assert(tests.some(t => t.id === id), 'missing '+id);
    for (const stage of ['R2','R3','R4']) assert(tests.some(t => t.stage === stage));
    assert.deepEqual(Object.keys(qaFixtures).sort(), ['basic','crossing','tl494','twoNets']);
  });
  it('pins the authentic frozen E695 provenance and counts', () => {
    assert.equal(source.sha, 'e695c415fdced164b0e0c39c5249d030795a0aa6');
    assert.deepEqual([
      source.components,source.nets,source.pinMemberships,
      source.da1PhysicalPins,source.nonElectricalBContinuations,
    ], [23,15,62,16,2]);
  });
  it('detects broken tests and avoids accidental green CI', () => {
    const errors = validateManifest([
      {...tests[0],id:'malformed',fixture:'missing'},tests[0],tests[0]
    ]);
    assert(errors.some(e => e.startsWith('bad id:')));
    assert(errors.some(e => e.startsWith('unknown fixture:')));
    assert(errors.some(e => e.startsWith('duplicate id:')));
  });
});
