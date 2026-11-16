/** Export boundary: electrical model is held by #122/#123, not the DOM or SVG. */
export type ExportKind = 'svg' | 'png';
export type PageFormat = 'A4' | 'A3' | 'A2';
export type Orientation = 'portrait' | 'landscape';
export type PointUm = readonly [number, number];
export type RegionUm = readonly [number, number, number, number];

/** Request is against an immutable validated model snapshot (CAS source hash). */
export interface ExportRequestV1 {
  protocol: 'gscad-export';
  protocol_version: 1;
  project_sha256: string;
  sheet_id: string;
  format: ExportKind;
  page: PageFormat;
  orientation: Orientation;
  region_um?: RegionUm;
  dpi: number;
  include_frame: boolean;
  include_title: boolean;
  background: 'white' | 'transparent';
  /** Text must be outlined or renderer font identity verified; otherwise reject. */
  strict_font: boolean;
}

export interface ExportManifestV1 {
  protocol: 'gscad-export';
  protocol_version: 1;
  source_project_sha256: string;
  engine_svg_sha256: string;
  exported_file_sha256: string;
  physical_size_um: PointUm;
  raster_size_px?: PointUm;
  dpi?: number;
  warnings: readonly string[];
}

/**
 * This is a transport DTO, not a complete project schema.  #118 owns
 * protected OS filesystem/worker invocation, #122 owns ProjectFileV2,
 * #123 owns connectivity and explicit junctions.  No browser DOM screenshots.
 */
export type ExportRpcV1 = {
  method: 'render_export';
  params: ExportRequestV1;
  expected_project_sha256: string;
};
