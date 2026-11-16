/**
 * Visual CAD UX acceptance contract. Pure data for Node tests.
 * Owner CHAT1 #117; this is NOT evidence that a browser CAD app works.
 */
export const source = Object.freeze({
  sha: 'e695c415fdced164b0e0c39c5249d030795a0aa6',
  components: 23, nets: 15, pinMemberships: 62,
  da1PhysicalPins: 16, nonElectricalBContinuations: 2,
});

export const qaFixtures = Object.freeze({
  basic: 'qa-r-c',
  twoNets: 'qa-two-nets',
  crossing: 'qa-crossing',
  tl494: 'qa-e695-tl494',
});

export const tests = Object.freeze([
  { id:'CAD-UX-R2-01', stage:'R2', fixture:'basic', action:'Open project, catalog, canvas, tree, inspector, status',
    invariant:'Core controls visible and accessible; not screenshot-only shell' },
  { id:'CAD-UX-R2-02', stage:'R2', fixture:'basic', action:'Search resistor; place, move, rotate and undo via mouse and R',
    invariant:'Component ID and physical pin numbers unchanged across transforms and Undo' },
  { id:'CAD-UX-R2-03', stage:'R2', fixture:'basic', action:'Toggle gridVisible and snapEnabled independently',
    invariant:'Independent view flags and exact physical pin attachment with snap disabled' },
  { id:'CAD-UX-R2-04', stage:'R2', fixture:'basic', action:'Toggle themes and resize 1280/1440/1920',
    invariant:'Reachable controls and no window viewport horizontal overflow' },
  { id:'CAD-UX-R2-05', stage:'R2', fixture:'basic', action:'Type W in inspector; Ctrl+K palette; Esc',
    invariant:'Tool shortcut does not fire inside text input; focus remains visible' },
  { id:'CAD-UX-R3-01', stage:'R3', fixture:'twoNets', action:'W, pin, click orthogonal bend, click other pin',
    invariant:'Real stored pin anchors, orthogonal route and unmodified declared source Nets' },
  { id:'CAD-UX-R3-02', stage:'R3', fixture:'twoNets', action:'Drag middle segment, Undo, Redo',
    invariant:'Atomic geometry changes; exact restored vertices and original electrical graph' },
  { id:'CAD-UX-R3-03', stage:'R3', fixture:'crossing', action:'Draw unmarked same-Net and other-Net X crossings',
    invariant:'No inferred electrical connection and no hidden junction dot' },
  { id:'CAD-UX-R3-04', stage:'R3', fixture:'crossing', action:'Explicit T junction; test invisible splice',
    invariant:'Only authored T Junction draws a dot; splice is electrically degree-2/no dot' },
  { id:'CAD-UX-R3-05', stage:'R3', fixture:'twoNets', action:'Try wrong-Net route and 1µm moved anchor',
    invariant:'NET_CONFLICT and PIN_ANCHOR_MISMATCH rollback without revision/history changes' },
  { id:'CAD-UX-R3-06', stage:'R3', fixture:'twoNets', action:'Save/reopen; export canonical SVG and PNG300',
    invariant:'Source hash, 1µm, anchors persist; SVG vectors in mm and actual 300DPI PNG pHYs' },
  { id:'CAD-UX-R4-01', stage:'R4', fixture:'tl494', action:'Import frozen E695 and diagnose incomplete route',
    invariant:'23/15/62/16+2b, source-locked, no old 91/37 route marked verified' },
]);

export function validateManifest(items = tests) {
  const ids = new Set();
  const errors = [];
  for (const item of items) {
    if (!/^CAD-UX-R[234]-\d{2}$/.test(item.id)) errors.push('bad id: '+item.id);
    if (ids.has(item.id)) errors.push('duplicate id: '+item.id);
    ids.add(item.id);
    if (!['R2','R3','R4'].includes(item.stage)) errors.push('bad stage: '+item.id);
    if (!Object.hasOwn(qaFixtures, item.fixture)) errors.push('unknown fixture: '+item.fixture);
    if (!item.action || !item.invariant) errors.push('missing action or invariant: '+item.id);
  }
  return errors;
}
