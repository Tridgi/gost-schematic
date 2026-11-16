/** Typed view coordinate interface. Integer µm are authoritative; pixels only for selection. */
import type { PinRef } from '../model/contract';
import type { CanvasScene, CanvasSymbol } from './scene-projection.mjs';
export type PointUm = [number,number];
export type Camera = {s:number;x:number;y:number};
export type ScreenPoint = {x:number;y:number};
export type VisualHit =
 | ({kind:'pin';pin:PinRef;at_um:PointUm;normal:string;distance_px:number})
 | ({kind:'ambiguous-pin';candidates:PinRef[]})
 | ({kind:'junction';junction_id:string})
 | ({kind:'segment';wire_id:string;segment_id:string;distance_px:number;movable:boolean;axis:'h'|'v'})
 | ({kind:'ambiguous-segment';candidates:{wire_id:string;segment_id:string}[]});
export declare function assertUm(value:number):number;
export declare function point(value:readonly number[]):PointUm;
export declare function camera(c:Camera):Camera;
export declare function screen(p:readonly number[],c:Camera):ScreenPoint;
export declare function world(p:ScreenPoint,c:Camera):PointUm;
export declare function zoom(c:Camera,p:ScreenPoint,factor:number):Camera;
export declare function snap(p:PointUm,grid:number,enabled:boolean):PointUm;
export declare function pinWorld(symbol:CanvasSymbol,number:string):{at_um:PointUm;normal:string;pin:PinRef};
export declare function hitTest(scene:CanvasScene,c:Camera,p:ScreenPoint,tolerance?:number):VisualHit|null;
