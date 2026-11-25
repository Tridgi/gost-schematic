/** Types for the read-only canonical model -> viewport projection.
 * Bound to scene-projection.mjs; signed coordinates remain integer micrometres.
 * Neither this API nor the view can write source Nets or attach electrical pins.
 */
import type { ProjectFileV2, WirePolyline, Junction, Splice, ConstantAnnotation } from '../model/contract';

export type PointUm = [number, number];
export type CanvasPinNormal = 'left'|'right'|'up'|'down';
export type CanvasPin = {
  physical_pin_number:string;
  at_um:PointUm;
  normal:CanvasPinNormal;
};
export type CanvasStroke = {from_um:PointUm;to_um:PointUm;stroke_um?:number};
export type CanvasSymbol = {
  instance_id:string;
  component_id:string;
  origin_um:PointUm;
  rotation_deg:0|90|180|270;
  mirror_x:boolean;
  pins:CanvasPin[];
  strokes:CanvasStroke[];
  inkStrokes:(CanvasStroke&{stroke_um:number})[];
  curves:{kind:'circle'|'semicircle';points_um:PointUm[];stroke_um:number;center:PointUm;radius:number;sweep:0|1;bounds:PointUm[]}[];
  notes:ConstantAnnotation[];
  status:'draft'|'approved'|'deprecated';
  layer_id:string;
};
export type CanvasGraphic = {
  id:string;
  layer_id:string;
  kind:'line'|'polyline'|'source_b_continuation';
  source_role:string;
  electrical:false;
  strokes:CanvasStroke[];
};
export type CanvasScene = {
  symbols:CanvasSymbol[];
  wires:WirePolyline[];
  junctions:Junction[];
  splices:Splice[];
  graphics:CanvasGraphic[];
};
/** Rejects unknown version/part/symbol/pin/graphic; never mutates its input. */
export declare function projectToCanvasScene(file:ProjectFileV2,sheetId:string):CanvasScene;
