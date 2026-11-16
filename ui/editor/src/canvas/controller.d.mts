/** Events from a view-only pointer state machine: electrical mutations belong to the host. */
import type { PinRef } from '../model/contract';
import type { WiringSnapshot } from '../wires/manual-wire';
import type { CanvasScene } from './scene-projection.mjs';
import type { Camera,PointUm,VisualHit,ScreenPoint } from './precision.mjs';
import type { SegmentDragToken } from './wire-intents.mjs';
export type CanvasIntent =
 | {kind:'beginWire';pin:PinRef}
 | {kind:'commitWire';source:PinRef;target:{kind:'pin';pin:PinRef}|{kind:'free';at_um:PointUm};bend_points_um:PointUm[]}
 | {kind:'cancelWire';source:PinRef}
 | {kind:'moveSegment';token:SegmentDragToken;delta_um:number}
 | {kind:'moveInstance';component_id:string;instance_id:string;delta_um:PointUm;base_revision:number}
 | {kind:'rotateInstance';component_id:string;instance_id:string;base_revision:number}
 | {kind:'select';target:VisualHit|{kind:'symbol';instance_id:string;component_id:string;distance_px:number}|{kind:'ambiguous-symbol';candidates:string[]}|null};
export type CanvasContext={
 scene:CanvasScene;wireSnapshot:WiringSnapshot;camera:Camera;
 tool:'select'|'wire'|'pan'|'text';gridUm:number;snapEnabled:boolean;
 onIntent:(intent:CanvasIntent)=>void;
};
export type PointerPoint=ScreenPoint & {pointerId:number;button:number};
export type CanvasControllerState={
 camera:Camera;draft:null|{source:PinRef;from_um:PointUm;bends_um:PointUm[];cursor_um:PointUm};
 drag:null|{kind:'pan'|'segment';pointerId:number};
 hover:VisualHit|null;
 selected:VisualHit|{kind:'symbol';instance_id:string;component_id:string;distance_px:number}|null;
};
export type CanvasController={
 getState():CanvasControllerState;
 setContext(next:Partial<CanvasContext>):void;
 down(p:PointerPoint):boolean;
 move(p:PointerPoint):boolean;
 up(p:PointerPoint):boolean;
 key(k:string):boolean;
 preview():PointUm[];
};
export declare function createCanvasController(context:CanvasContext):CanvasController;
