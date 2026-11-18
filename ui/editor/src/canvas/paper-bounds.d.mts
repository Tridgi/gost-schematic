import type { CanvasScene } from './scene-projection.mjs';
import type { WiringSnapshot } from '../wires/manual-wire';
export type PaperOverflow = {symbols:string[];graphics:string[];wires:string[];
 junctions:string[];splices:string[];total:number};
export declare function detectPaperOverflow(scene:CanvasScene,
 snapshot:WiringSnapshot,sizeUm:readonly [number,number]):PaperOverflow;
