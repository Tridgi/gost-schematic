/** UI-only persistent geometry: never serialize these values into the electrical Project. */
export type DockLayout = { navbar?: number; aside?: number; inspectorPercent?: number };
export const DOCK_LAYOUT_KEY = 'gscad:ui:dock-layout:v1';

export function normalizeDockLayout(value: unknown, viewportWidth = 1440): DockLayout {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  const candidate = value as Record<string, unknown>;
  const width = Number.isFinite(viewportWidth) && viewportWidth > 0 ? viewportWidth : 1440;
  const available = Math.max(0, width - 420); // Reserve width for CAD canvas where possible.
  const output: DockLayout = {};
  const valid = (x: unknown): x is number => typeof x === 'number' && Number.isFinite(x);
  if (valid(candidate.navbar)) output.navbar = Math.min(420, Math.max(200, candidate.navbar));
  if (valid(candidate.aside)) output.aside = Math.min(460, Math.max(260, candidate.aside));
  if (output.navbar !== undefined && output.aside !== undefined && output.navbar + output.aside > available) {
    const excess = output.navbar + output.aside - available;
    const leftReduction = Math.min(excess, output.navbar - 200);
    output.navbar -= leftReduction;
    output.aside = Math.max(260, output.aside - (excess - leftReduction));
  }
  if (valid(candidate.inspectorPercent)) output.inspectorPercent = Math.min(75, Math.max(25, candidate.inspectorPercent));
  return output;
}

export function safeLayoutFromJSON(raw: string | null, width?: number): DockLayout {
  if (!raw) return {};
  try { return normalizeDockLayout(JSON.parse(raw), width); } catch { return {}; }
}
export function layoutForStorage(layout: DockLayout): string {
  return JSON.stringify(normalizeDockLayout(layout));
}
