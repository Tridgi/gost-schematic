/**
 * CHAT1 / #117: QA-only read-only bridge for canonical v2 source_b_continuation.
 *
 * This proves that a #122 source graphic can be projected without becoming an
 * electrical wire. It is NOT a substitute for the #120 production fix.
 * Never persist the normalized copy: gscad-project v2 source remains unchanged.
 */
import { projectToCanvasScene } from '../editor/src/canvas/scene-projection.mjs';

const safePoint = p => Array.isArray(p) && p.length === 2 &&
  p.every(n => Number.isSafeInteger(n) && Math.abs(n) <= 1_000_000_000);

export function projectForUXReview(file, sheetId) {
  if (!file || file.format !== 'gscad-project' || file.format_version !== 2 ||
      !Array.isArray(file.project?.sheets)) throw Error('UNSUPPORTED_PROJECT_V2');
  const sheet = file.project.sheets.find(s => s.id === sheetId);
  if (!sheet || !Array.isArray(sheet.graphics)) throw Error('UNKNOWN_SHEET');
  const sourceB = new Set();
  const graphics = sheet.graphics.map(g => {
    if (g.kind !== 'source_b_continuation') return g;
    if (typeof g.id !== 'string' || !g.id.trim() || sourceB.has(g.id) ||
        typeof g.layer_id !== 'string' || !g.layer_id.trim() ||
        !Array.isArray(g.points_um) || g.points_um.length !== 2 ||
        !g.points_um.every(safePoint) ||
        g.points_um[0].every((n,i) => n === g.points_um[1][i]) ||
        !Number.isSafeInteger(g.stroke_um) || g.stroke_um <= 0 ||
        g.electrical === true) throw Error('INVALID_SOURCE_B_GRAPHIC');
    sourceB.add(g.id);
    // The existing graphicsToStrokes supports a line; keep the original
    // source semantics separately in the returned review-only scene.
    return { ...g, kind: 'line', source_role: 'source_b_continuation' };
  });
  const view = { ...file, project: {
    ...file.project,
    sheets: file.project.sheets.map(s => s === sheet ? {...s, graphics} : s)
  }};
  const scene = projectToCanvasScene(view, sheetId);
  return { ...scene, graphics: scene.graphics.map(g => sourceB.has(g.id)
    ? { ...g, kind: 'source_b_continuation',
        source_role: 'source_b_continuation', electrical: false }
    : g) };
}
