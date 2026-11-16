import { useCallback, useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent, type WheelEvent as ReactWheelEvent } from 'react';
import type { ProjectFileV2 } from '../model/contract';
import type { WiringSnapshot } from '../wires/manual-wire';
import { projectToCanvasScene, type CanvasScene, type CanvasSymbol } from './scene-projection.mjs';
import { pinWorld, screen, zoom, type Camera, type PointUm, type ScreenPoint } from './precision.mjs';
import { createCanvasController, type CanvasController, type CanvasIntent, type CanvasContext } from './controller.mjs';

export type CanvasViewportProps = {
  document: ProjectFileV2;
  sheetId: string;
  snapshot: WiringSnapshot;
  tool: CanvasContext['tool'];
  gridVisible: boolean;
  snapEnabled: boolean;
  /** No electrical mutation is allowed inside the canvas; the host validates this command. */
  onIntent: (intent: CanvasIntent) => void;
  onZoomPercent?: (percent: number) => void;
};

const DEFAULT_CAMERA:Camera={s:.004,x:24,y:24};
const asCoords=(p:ScreenPoint)=>({x:p.x,y:p.y});
const g2=(n:number)=>Number.isFinite(n)?n:0;
function localStroke(symbol:CanvasSymbol,p:PointUm,camera:Camera):ScreenPoint {
  const x=symbol.mirror_x?-p[0]:p[0],y=p[1];
  const xy=symbol.rotation_deg===0?[x,y]:symbol.rotation_deg===90?[-y,x]:
    symbol.rotation_deg===180?[-x,-y]:[y,-x];
  return screen([symbol.origin_um[0]+xy[0],symbol.origin_um[1]+xy[1]],camera);
}
/** Read-only SVG viewport. The canonical physical print/export belongs to #124. */
export function CanvasViewport({document,sheetId,snapshot,tool,gridVisible,snapEnabled,onIntent,onZoomPercent}:CanvasViewportProps){
  const svgRef=useRef<SVGSVGElement|null>(null);
  const [size,setSize]=useState({width:960,height:640});
  const [revision,setRevision]=useState(0);
  const cameraRef=useRef<Camera>({...DEFAULT_CAMERA});
  const scene=useMemo(()=>projectToCanvasScene(document,sheetId),[document,sheetId]);
  // Snapshot carries the real #123 wire edits; original serialized routes are only the initial view.
  const visibleScene=useMemo<CanvasScene>(()=>({...scene,wires:snapshot.wires,junctions:snapshot.junctions,splices:snapshot.splices}),[scene,snapshot]);
  const callbackRef=useRef(onIntent);
  callbackRef.current=onIntent;
  const controllerRef=useRef<CanvasController|null>(null);
  if(!controllerRef.current){
    controllerRef.current=createCanvasController({
      scene:visibleScene,wireSnapshot:snapshot,camera:cameraRef.current,tool,
      gridUm:document.project.settings.grid_step_um,snapEnabled,
      onIntent:intent=>callbackRef.current(intent)
    });
  }
  const controller=controllerRef.current;
  controller.setContext({
    scene:visibleScene,wireSnapshot:snapshot,tool,snapEnabled,
    gridUm:document.project.settings.grid_step_um,onIntent:intent=>callbackRef.current(intent)
  });
  const invalidate=useCallback(()=>{setRevision(n=>n+1)},[]);
  const fittedRef=useRef<string|null>(null);
  /** Initial camera fits the actual signed E695 scene, not a hardcoded sheet corner.
   * A pin outside the visible viewport is not an actionable CAD endpoint.
   */
  useEffect(()=>{
    const identity=document.project.id+':'+sheetId;
    if(fittedRef.current===identity)return;
    const bounds=svgRef.current?.getBoundingClientRect();
    if(!bounds||bounds.width<100||bounds.height<100)return;
    const all:PointUm[]=[];
    for(const symbol of scene.symbols){
      all.push(symbol.origin_um);
      for(const pin of symbol.pins)all.push(pinWorld(symbol,pin.physical_pin_number).at_um);
    }
    for(const g of scene.graphics)for(const stroke of g.strokes){
      all.push(stroke.from_um,stroke.to_um);
    }
    if(!all.length)return;
    const minX=Math.min(...all.map(p=>p[0])),maxX=Math.max(...all.map(p=>p[0]));
    const minY=Math.min(...all.map(p=>p[1])),maxY=Math.max(...all.map(p=>p[1]));
    // 32 CSS pixels minimum around all physical contacts, including the source b ink.
    const scale=Math.max(.0002,Math.min(.02,
      (bounds.width-64)/Math.max(1000,maxX-minX),
      (bounds.height-64)/Math.max(1000,maxY-minY)));
    const fitted:Camera={
      s:scale,x:bounds.width/2-((minX+maxX)/2)*scale,
      y:bounds.height/2-((minY+maxY)/2)*scale
    };
    controller.setContext({camera:fitted});
    fittedRef.current=identity;
    onZoomPercent?.(Math.round(fitted.s/DEFAULT_CAMERA.s*100));
    invalidate();
  },[scene,controller,document.project.id,sheetId,size.width,size.height,invalidate,onZoomPercent]);
  useEffect(()=>{
    const root=svgRef.current;
    if(!root||typeof ResizeObserver==='undefined')return;
    const observer=new ResizeObserver(entries=>{
      const rect=entries[0]?.contentRect;
      if(rect&&rect.width>0&&rect.height>0)setSize({width:rect.width,height:rect.height});
    });
    observer.observe(root);
    return ()=>observer.disconnect();
  },[]);
  const camera=controller.getState().camera;
  cameraRef.current=camera;
  const local=useCallback((e:{clientX:number;clientY:number}):ScreenPoint=>{
    const r=svgRef.current?.getBoundingClientRect();
    return {x:e.clientX-(r?.left??0),y:e.clientY-(r?.top??0)};
  },[]);
  const eventPoint=(e:ReactPointerEvent<SVGSVGElement>)=>({...local(e),pointerId:e.pointerId,button:e.button});
  const down=(e:ReactPointerEvent<SVGSVGElement>)=>{
    if(controller.down(eventPoint(e))){
      e.preventDefault();e.currentTarget.focus();
      if(!e.currentTarget.hasPointerCapture(e.pointerId))e.currentTarget.setPointerCapture(e.pointerId);
      invalidate();
    }
  };
  const move=(e:ReactPointerEvent<SVGSVGElement>)=>{controller.move(eventPoint(e));invalidate()};
  const up=(e:ReactPointerEvent<SVGSVGElement>)=>{
    controller.up(eventPoint(e));
    if(e.currentTarget.hasPointerCapture(e.pointerId))e.currentTarget.releasePointerCapture(e.pointerId);
    invalidate();
  };
  const wheel=(e:ReactWheelEvent<SVGSVGElement>)=>{
    e.preventDefault();
    controller.setContext({camera:zoom(controller.getState().camera,local(e),e.deltaY<0?1.15:.85)});
    onZoomPercent?.(Math.round(controller.getState().camera.s/DEFAULT_CAMERA.s*100));
    invalidate();
  };
  const vertices=(snapshotWire:WiringSnapshot['wires'][number])=>new Map(snapshotWire.vertices.map(v=>[v.id,v.at_um]));
  const step=document.project.settings.grid_step_um*camera.s;
  const grid=gridVisible&&step>=6&&Number.isFinite(step);
  // Revision forces deliberate repaint of hover / drag preview without storing any Net state.
  void revision;
  return <svg ref={svgRef} className="gscad-drawing" role="img" tabIndex={0}
    data-testid="gscad-signed-svg-canvas" aria-label="Редактор электрической схемы, координаты в микрометрах"
    viewBox={`0 0 ${g2(size.width)} ${g2(size.height)}`}
    onPointerDown={down} onPointerMove={move} onPointerUp={up}
    onPointerCancel={e=>{controller.key('Escape');if(e.currentTarget.hasPointerCapture(e.pointerId))e.currentTarget.releasePointerCapture(e.pointerId);invalidate()}}
    onWheel={wheel}
    onKeyDown={e=>{if(['Escape','Enter','r','R'].includes(e.key)){if(controller.key(e.key)){e.preventDefault();invalidate()}}}}
    style={{touchAction:'none',outlineOffset:2}}>
    <defs>
      {grid&&<pattern id="cad-grid-um" width={step} height={step}
        patternUnits="userSpaceOnUse"
        patternTransform={`translate(${((camera.x%step)+step)%step} ${((camera.y%step)+step)%step})`}>
        <path d={`M ${step} 0 L 0 0 0 ${step}`} fill="none" stroke="#bbc5cb" strokeWidth={.5}/>
      </pattern>}
    </defs>
    <rect width="100%" height="100%" fill="#fbfcfe"/>
    {grid&&<rect width="100%" height="100%" fill="url(#cad-grid-um)" pointerEvents="none"/>}
    <g className="non-electrical-source-ink" fill="none" stroke="#947858" strokeWidth={1.2} pointerEvents="none">
      {visibleScene.graphics.map(g=><g key={g.id} data-electrical="false" data-source-role={g.source_role}>
        {g.strokes.map((stroke,i)=>{
          const a=screen(stroke.from_um,camera),b=screen(stroke.to_um,camera);
          return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}/>;
        })}
      </g>)}
    </g>
    <g className="symbol-ugo" fill="none" stroke="#24384b" strokeWidth={1.5} pointerEvents="none">
      {visibleScene.symbols.map(s=><g key={s.instance_id} data-component-id={s.component_id}
        data-selected={String(controller.getState().selected?.kind==='symbol'&&controller.getState().selected?.instance_id===s.instance_id)}
        data-testid={'symbol-'+(document.project.components.find(c=>c.id===s.component_id)?.refdes??s.component_id)}
        stroke={controller.getState().selected?.kind==='symbol'&&controller.getState().selected?.instance_id===s.instance_id?'#e29225':undefined}>
        {s.strokes.map((stroke,i)=>{
          const a=localStroke(s,stroke.from_um,camera),b=localStroke(s,stroke.to_um,camera);
          return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}/>;
        })}
      </g>)}
    </g>
    <g className="electric-wires" fill="none" stroke="#22799e" strokeWidth={1.9} pointerEvents="none">
      {snapshot.wires.map(w=>{
        const map=vertices(w);
        return <g key={w.id} data-wire-id={w.id} data-net-id={w.net_id}>
          {w.segments.map(seg=>{
            const a=map.get(seg.from_vertex_id),b=map.get(seg.to_vertex_id);
            if(!a||!b)throw Error('MISSING_VERTEX');
            const v=screen(a,camera),u=screen(b,camera);
            return <line key={seg.id} data-segment-id={seg.id}
              x1={v.x} y1={v.y} x2={u.x} y2={u.y}/>;
          })}
        </g>;
      })}
    </g>
    <g className="junction-dots" fill="#22799e" pointerEvents="none">
      {snapshot.junctions.map(j=>{
        const p=screen(j.at_um,camera);
        return <circle key={j.id} data-junction-id={j.id} cx={p.x} cy={p.y} r={3.1}/>;
      })}
    </g>
    <g className="physical-pin-markers" fill="#fff" stroke="#237f69" strokeWidth={1.35} pointerEvents="all">
      {visibleScene.symbols.flatMap(s=>s.pins.map(pin=>{
        const p=screen(pinWorld(s,pin.physical_pin_number).at_um,camera);
        return <circle key={s.instance_id+':'+pin.physical_pin_number}
          data-testid={'signed-pin-'+s.component_id+'-'+pin.physical_pin_number}
          cx={p.x} cy={p.y} r={3}/>;
      }))}
    </g>
    <g className="draft-preview" fill="none" stroke="#d58c27" strokeWidth={1.8}
      strokeDasharray="6 3" pointerEvents="none">
      {controller.preview().slice(1).map((p,i)=>{
        const prev=controller.preview()[i],a=screen(prev,camera),b=screen(p,camera);
        return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}/>;
      })}
    </g>
  </svg>;
}
export default CanvasViewport;
