import type { CanvasScene } from './scene-projection.mjs';
import type { WiringSnapshot } from '../wires/manual-wire';
export type PaperOverflow = {symbols:string[];graphics:string[];wires:string[];
 junctions:string[];splices:string[];texts:string[];total:number};
export declare function detectPaperOverflow(scene:CanvasScene,
 snapshot:WiringSnapshot,sizeUm:readonly [number,number],annotations?:readonly {id:string;text:string;at_um:readonly [number,number];height_um?:number;rotation_deg?:0|90|180|270}[]):PaperOverflow;
