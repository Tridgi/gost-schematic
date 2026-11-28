/** Events from a view-only pointer state machine: electrical mutations belong to the host. */
import type { PinRef } from '../model/contract';
import type { WiringSnapshot } from '../wires/manual-wire';
import type { CanvasScene } from './scene-projection.mjs';
import type { Camera,PointUm,VisualHit,ScreenPoint } from './precision.mjs';
import type { SegmentDragToken } from './wire-intents.mjs';
export type JunctionWireSource={kind:'junction';junction_id:string;at_um:PointUm;base_revision:number};
export type CanvasIntent =
 | {kind:'beginJunctionWire';source:JunctionWireSource}
 | {kind:'commitJunctionWire';source:JunctionWireSource;pin:PinRef;bend_points_um:PointUm[]}
 | {kind:'cancelJunctionWire';source:JunctionWireSource}
 | {kind:'beginWire';pin:PinRef}
 | {kind:'commitWire';source:PinRef;target:{kind:'pin';pin:PinRef}|{kind:'free';at_um:PointUm}|{kind:'segment';wire_id:string;segment_id:string;at_um:PointUm}|{kind:'junction';junction_id:string;at_um:PointUm};bend_points_um:PointUm[];base_revision?:number}
 | {kind:'cancelWire';source:PinRef}
 | {kind:'placeSymbol';at_um:PointUm;base_revision:number}
 | {kind:'placeText';at_um:PointUm;base_revision:number}
 | {kind:'moveText';text_id:string;at_um:PointUm;base_revision:number}
 | {kind:'deleteText';text_id:string;base_revision:number}
 | {kind:'rotateText';text_id:string;direction:1|-1;base_revision:number}
 | {kind:'deleteSymbol';component_id:string;instance_id:string;base_revision:number}
 | {kind:'deleteWire';wire_id:string;base_revision:number}
 | {kind:'moveSegment';token:SegmentDragToken;delta_um:number}
 | {kind:'createJunction';selected_segments:readonly {wire_id:string;segment_id:string}[];base_revision:number}
 | {kind:'rejectJunction';reason:string}
 | {kind:'moveInstance';component_id:string;instance_id:string;delta_um:PointUm;base_revision:number}
 | {kind:'rotateInstance';component_id:string;instance_id:string;base_revision:number}
 | {kind:'selectGroup';instance_ids:string[];base_revision:number}
 | {kind:'moveGroup';instance_ids:string[];delta_um:PointUm;base_revision:number}
 | {kind:'select';target:VisualHit|{kind:'symbol';instance_id:string;component_id:string;distance_px:number}|{kind:'ambiguous-symbol';candidates:string[]}|null};
export type CanvasContext={
 scene:CanvasScene;wireSnapshot:WiringSnapshot;camera:Camera;
 tool:'select'|'wire'|'pan'|'text'|'junction'|'place';gridUm:number;snapEnabled:boolean;canTap?:boolean;
 onIntent:(intent:CanvasIntent)=>void|boolean;
};
export type PointerPoint=ScreenPoint & {pointerId:number;button:number;ctrlKey?:boolean;shiftKey?:boolean};
export type CanvasControllerState={
 camera:Camera;draft:null|{source:PinRef|JunctionWireSource;from_um:PointUm;bends_um:PointUm[];cursor_um:PointUm};
 drag:null|{kind:'pan'|'segment'|'symbol'|'marquee'|'group';pointerId:number};
 hover:VisualHit|null;
 selectedGroup:string[];
 selected:VisualHit|{kind:'symbol';instance_id:string;component_id:string;distance_px:number}|null;
};
export type CanvasController={
 getState():CanvasControllerState;
 tapPreview():null|{kind:'segment';wire_id:string;segment_id:string;at_um:PointUm}|{kind:'junction';junction_id:string;at_um:PointUm};
 clearTapPreview():void;
 symbolDragPreview():null|{instance_id:string;component_id:string;delta_um:PointUm};
 marqueePreview():null|{x:number;y:number;width:number;height:number};
 groupDragPreview():null|{instance_ids:string[];delta_um:PointUm};
 setContext(next:Partial<CanvasContext>):void;
 syncSymbolSelection(instanceId:string|null,clearOther?:boolean,groupIds?:readonly string[]):void;
 contextSelect(p:ScreenPoint):'symbol'|'group'|'blank'|null;
 down(p:PointerPoint):boolean;
 move(p:PointerPoint):boolean;
 up(p:PointerPoint):boolean;
 key(k:string):boolean;
 preview():PointUm[];
};
export declare function createCanvasController(context:CanvasContext):CanvasController;
