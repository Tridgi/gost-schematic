import { useCallback, useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent, type WheelEvent as ReactWheelEvent, type MouseEvent as ReactMouseEvent } from 'react';
import {noteLayout} from '../model/symbol-notes.mjs';
import { createPortal } from 'react-dom';
import type { PlacementHint } from '../authoring/session';
import type { ProjectFileV2 } from '../model/contract';
import type { WiringSnapshot } from '../wires/manual-wire';
import { projectToCanvasScene, type CanvasScene, type CanvasSymbol } from './scene-projection.mjs';
import { pinWorld, screen, zoom, world, snap, type Camera, type PointUm, type ScreenPoint } from './precision.mjs';
import { createCanvasController, type CanvasController, type CanvasIntent, type CanvasContext } from './controller.mjs';

export type CanvasViewportProps = {
  document: ProjectFileV2;
  sheetId: string;
  snapshot: WiringSnapshot;
  tool: CanvasContext['tool'];
  gridVisible: boolean;
  snapEnabled: boolean;
  /** No electrical mutation is allowed inside the canvas; the host validates this command. */
  onIntent: (intent: CanvasIntent) => void|boolean;
  onZoomPercent?: (percent: number) => void;
  zoomRequest?: {percent:50|100|200;token:number};
  fitRequest?:number;
  selectedInstanceId:string|null;
  selectedGroupIds:readonly string[];
  selectionReset:number;
  canEdit?:boolean;
  placementHint?:(origin:readonly number[])=>PlacementHint|null;
  onCopy?:()=>void;
  onPaste?:()=>void;
  onFitPage?:()=>void;
};

const DEFAULT_CAMERA:Camera={s:.004,x:24,y:24};
const asCoords=(p:ScreenPoint)=>({x:p.x,y:p.y});
const g2=(n:number)=>Number.isFinite(n)?n:0;
function localStroke(symbol:CanvasSymbol,p:readonly [number,number],camera:Camera):ScreenPoint {
  const x=symbol.mirror_x?-p[0]:p[0],y=p[1];
  const xy=symbol.rotation_deg===0?[x,y]:symbol.rotation_deg===90?[-y,x]:
    symbol.rotation_deg===180?[-x,-y]:[y,-x];
  return screen([symbol.origin_um[0]+xy[0],symbol.origin_um[1]+xy[1]],camera);
}
function SymbolInk({symbol,camera}:{symbol:CanvasSymbol;camera:Camera}){
 return <>
  {symbol.inkStrokes.map((stroke,i)=>{
   const a=localStroke(symbol,stroke.from_um,camera),b=localStroke(symbol,stroke.to_um,camera);
   return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} strokeWidth={Math.max(.65,stroke.stroke_um*camera.s)}/>;
  })}
  {symbol.curves.map((curve,i)=>{
   const center=localStroke(symbol,curve.center,camera),radius=curve.radius*camera.s;
   const width=Math.max(.65,curve.stroke_um*camera.s);
   if(curve.kind==='circle')return <circle key={i} data-ugo-curve="circle" cx={center.x} cy={center.y} r={radius} strokeWidth={width}/>;
   const a=localStroke(symbol,curve.points_um[0],camera),b=localStroke(symbol,curve.points_um[2],camera);
   const sweep=symbol.mirror_x?1-curve.sweep:curve.sweep;
   return <path key={i} data-ugo-curve="semicircle" d={`M ${a.x} ${a.y} A ${radius} ${radius} 0 0 ${sweep} ${b.x} ${b.y}`} strokeWidth={width}/>;
  })}
  {symbol.notes.map(n=>{
   const at=localStroke(symbol,n.at_um,camera);
   const h=n.height_um*camera.s,y=at.y+(n.vertical==='top'?h:n.vertical==='center'?Math.round(n.height_um/3)*camera.s:0);
   return <text key={n.key} data-symbol-note={n.key} data-electrical="false" x={at.x} y={y}
     textAnchor={noteLayout(n,n.at_um).anchor} fontSize={Math.max(6,h)} fontFamily="sans-serif"
     fill="#24384b" stroke="none">{n.text}</text>;
  })}
 </>;
}
/** Read-only SVG viewport. The canonical physical print/export belongs to #124. */
export function CanvasViewport({document,sheetId,snapshot,tool,gridVisible,snapEnabled,onIntent,onZoomPercent,zoomRequest,fitRequest,selectedInstanceId:hostSelectedId,selectedGroupIds,selectionReset,canEdit,placementHint,onCopy,onPaste,onFitPage}:CanvasViewportProps){
  const svgRef=useRef<SVGSVGElement|null>(null);
  const [size,setSize]=useState({width:960,height:640});
  const [revision,setRevision]=useState(0);
  const [placementPointer,setPlacementPointer]=useState<ScreenPoint|null>(null);
  const [contextMenu,setContextMenu]=useState<{x:number;y:number;kind:'symbol'|'group'|'blank';revision:number}|null>(null);
  const menuRef=useRef<HTMLDivElement|null>(null);
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
  const selectionResetRef=useRef(selectionReset);
  controller.syncSymbolSelection(hostSelectedId,selectionResetRef.current!==selectionReset,selectedGroupIds);
  selectionResetRef.current=selectionReset;
  const invalidate=useCallback(()=>{setRevision(n=>n+1)},[]);
  const fittedRef=useRef<string|null>(null);
  const appliedZoomRef=useRef<number|null>(null);
  const appliedZoomTokenRef=useRef<number|null>(null);
  /** Initial camera fits the actual signed E695 scene, not a hardcoded sheet corner.
   * A pin outside the visible viewport is not an actionable CAD endpoint.
   */
  useEffect(()=>{
    const identity=document.project.id+':'+sheetId+':'+
      document.project.sheets.find(s=>s.id===sheetId)?.frame.size_um.join('x')+':'+fitRequest;
    if(fittedRef.current===identity)return;
    const bounds=svgRef.current?.getBoundingClientRect();
    if(!bounds||bounds.width<100||bounds.height<100)return;
    const all:PointUm[]=[];
    // R10: fit the authoritative physical sheet, not just its populated ink.
    // A small populated circuit must not zoom so far that the A4/A3/A2 page
    // and its print margins disappear beyond the viewport.
    const frame=document.project.sheets.find(s=>s.id===sheetId)?.frame;
    if(frame)all.push([0,0],[frame.size_um[0],frame.size_um[1]]);
    for(const symbol of scene.symbols){
      all.push(symbol.origin_um);
      for(const pin of symbol.pins)all.push(pinWorld(symbol,pin.physical_pin_number).at_um);
    }
    for(const g of scene.graphics)for(const stroke of g.strokes){
      all.push(stroke.from_um,stroke.to_um);
    }
    if(!all.length){
      // A new empty A3 sheet must have a stable paper camera BEFORE first
      // placement. Never auto-fit only R1 after its first click: that would
      // unexpectedly relocate the viewport while placing C1.
      const sheet=document.project.sheets.find(s=>s.id===sheetId);
      if(!sheet)return;
      const [paperWidth,paperHeight]=sheet.frame.size_um;
      const scale=Math.min(.02,(bounds.width-64)/paperWidth,(bounds.height-64)/paperHeight);
      const fitted:Camera={s:scale,x:bounds.width/2-paperWidth*scale/2,
        y:bounds.height/2-paperHeight*scale/2};
      controller.setContext({camera:fitted});
      fittedRef.current=identity;
      appliedZoomRef.current=Math.round(scale/DEFAULT_CAMERA.s*100);
      onZoomPercent?.(appliedZoomRef.current);
      invalidate();
      return;
    }
    const minX=Math.min(...all.map(p=>p[0])),maxX=Math.max(...all.map(p=>p[0]));
    const minY=Math.min(...all.map(p=>p[1])),maxY=Math.max(...all.map(p=>p[1]));
    // 32 CSS pixels minimum around all physical contacts, including the source b ink.
    const scale=Math.min(.02,
      (bounds.width-64)/Math.max(1000,maxX-minX),
      (bounds.height-64)/Math.max(1000,maxY-minY));
    const fitted:Camera={
      s:scale,x:bounds.width/2-((minX+maxX)/2)*scale,
      y:bounds.height/2-((minY+maxY)/2)*scale
    };
    controller.setContext({camera:fitted});
    fittedRef.current=identity;
    const fittedPercent=Math.round(fitted.s/DEFAULT_CAMERA.s*100);
    appliedZoomRef.current=fittedPercent;
    onZoomPercent?.(fittedPercent);
    invalidate();
  },[scene,controller,document.project.id,sheetId,fitRequest,size.width,size.height,invalidate,onZoomPercent]);
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
  useEffect(()=>{
    // Do NOT reinterpret the auto-fit status update as a user-selected 100% zoom.
    // Only a distinct explicit menu token may replace the fitted camera.
    if(fittedRef.current===null||!zoomRequest||
      zoomRequest.token===appliedZoomTokenRef.current)return;
    const current=controller.getState().camera;
    const factor=(DEFAULT_CAMERA.s*zoomRequest.percent/100)/current.s;
    const center={x:size.width/2,y:size.height/2};
    controller.setContext({camera:zoom(current,center,factor)});
    appliedZoomRef.current=zoomRequest.percent;
    appliedZoomTokenRef.current=zoomRequest.token;
    invalidate();
  },[zoomRequest,controller,size.width,size.height,invalidate]);
  const camera=controller.getState().camera;
  cameraRef.current=camera;
  // Derive guide from current tool, model and pointer; no post-render reset race.
  let placementGuide:PlacementHint|null=null;
  if(tool==='place'&&placementHint&&placementPointer){
    try{placementGuide=placementHint(snap(world(placementPointer,camera),document.project.settings.grid_step_um,snapEnabled));}
    catch{placementGuide=null;}
  }
  const local=useCallback((e:{clientX:number;clientY:number}):ScreenPoint=>{
    const r=svgRef.current?.getBoundingClientRect();
    return {x:e.clientX-(r?.left??0),y:e.clientY-(r?.top??0)};
  },[]);
  const eventPoint=(e:ReactPointerEvent<SVGSVGElement>)=>({...local(e),pointerId:e.pointerId,button:e.button});
  const down=(e:ReactPointerEvent<SVGSVGElement>)=>{
    setContextMenu(null);setPlacementPointer(null);
    if(controller.down(eventPoint(e))){
      e.preventDefault();e.currentTarget.focus();
      if(!e.currentTarget.hasPointerCapture(e.pointerId))e.currentTarget.setPointerCapture(e.pointerId);
      invalidate();
    }
  };
  const move=(e:ReactPointerEvent<SVGSVGElement>)=>{
    controller.move(eventPoint(e));
    setPlacementPointer(tool==='place'&&placementHint?local(e):null);
    invalidate();
  };
  const up=(e:ReactPointerEvent<SVGSVGElement>)=>{
    controller.up(eventPoint(e));
    if(e.currentTarget.hasPointerCapture(e.pointerId))e.currentTarget.releasePointerCapture(e.pointerId);
    invalidate();
  };
  const wheel=(e:ReactWheelEvent<SVGSVGElement>)=>{
    setContextMenu(null);
    e.preventDefault();
    if(controller.getState().drag)return;
    controller.setContext({camera:zoom(controller.getState().camera,local(e),e.deltaY<0?1.15:.85)});
    const p=Math.round(controller.getState().camera.s/DEFAULT_CAMERA.s*100);
    appliedZoomRef.current=p;onZoomPercent?.(p);
    invalidate();
  };
  const openContextMenu=(e:ReactMouseEvent<SVGSVGElement>)=>{
    e.preventDefault();setContextMenu(null);
    const kind=controller.contextSelect(local(e));
    if(!kind)return;
    setContextMenu({x:Math.max(6,Math.min(e.clientX,window.innerWidth-246)),
      y:Math.max(6,Math.min(e.clientY,window.innerHeight-255)),kind,revision:snapshot.revision});
    invalidate();
  };
  const dismissMenu=(restoreFocus=false)=>{
    setContextMenu(null);
    if(restoreFocus)svgRef.current?.focus();
  };
  useEffect(()=>{
    if(!contextMenu)return;
    menuRef.current?.querySelector<HTMLButtonElement>('button:not(:disabled)')?.focus();
    const outside=(event:PointerEvent)=>{
      if(event.target instanceof Node&&!menuRef.current?.contains(event.target))setContextMenu(null);
    };
    const escape=(event:KeyboardEvent)=>{
      if(event.key==='Escape'){
        event.preventDefault();event.stopPropagation();setContextMenu(null);svgRef.current?.focus();
      }
    };
    window.addEventListener('pointerdown',outside,true);
    window.addEventListener('keydown',escape,true);
    const blur=()=>setContextMenu(null);
    window.addEventListener('blur',blur);
    return ()=>{
      window.removeEventListener('pointerdown',outside,true);
      window.removeEventListener('keydown',escape,true);
      window.removeEventListener('blur',blur);
    };
  },[contextMenu]);
  useEffect(()=>{setContextMenu(null)},[snapshot.revision,tool,selectionReset]);
  const runMenu=(action:()=>void)=>{
    if(!contextMenu||contextMenu.revision!==snapshot.revision||tool!=='select'||controller.getState().drag||controller.getState().draft){
      dismissMenu(true);return;
    }
    dismissMenu(true);action();invalidate();
  };
  const menuCommands=contextMenu?[
    {label:'Копировать',key:'copy',enabled:contextMenu.kind!=='blank'&&!!onCopy,run:()=>onCopy?.()},
    {label:'Вставить',key:'paste',enabled:!!onPaste,run:()=>onPaste?.()},
    {label:'Повернуть на 90°',key:'rotate',enabled:contextMenu.kind==='symbol'&&!!canEdit,run:()=>controller.key('r')},
    {label:'Удалить УГО',key:'delete',enabled:contextMenu.kind==='symbol'&&!!canEdit,run:()=>controller.key('Delete')},
    {label:'Вписать лист',key:'fit',enabled:!!onFitPage,run:()=>onFitPage?.()}
  ]:[];
  const dragPreview=controller.symbolDragPreview();
  const dragSource=dragPreview&&visibleScene.symbols.find(s=>s.instance_id===dragPreview.instance_id&&s.component_id===dragPreview.component_id);
  const ghost:CanvasSymbol|null=dragSource&&dragPreview?{...dragSource,origin_um:[
    dragSource.origin_um[0]+dragPreview.delta_um[0],dragSource.origin_um[1]+dragPreview.delta_um[1]
  ]}:null;
  const groupDrag=controller.groupDragPreview();
  const groupGhosts:CanvasSymbol[]=groupDrag?visibleScene.symbols.filter(s=>groupDrag.instance_ids.includes(s.instance_id)).map((s):CanvasSymbol=>({...s,origin_um:[s.origin_um[0]+groupDrag.delta_um[0],s.origin_um[1]+groupDrag.delta_um[1]]})):[];
  const marquee=controller.marqueePreview();
  const selectedGroup=new Set(controller.getState().selectedGroup);
  const selectedSymbol=controller.getState().selected;
  const selectedInstanceId=selectedSymbol?.kind==='symbol'?selectedSymbol.instance_id:null;
  const vertices=(snapshotWire:WiringSnapshot['wires'][number])=>new Map(snapshotWire.vertices.map(v=>[v.id,v.at_um]));
  const step=document.project.settings.grid_step_um*camera.s;
  const grid=gridVisible&&step>=6&&Number.isFinite(step);
  const pageFrame=document.project.sheets.find(sh=>sh.id===sheetId)?.frame;
  const pageStart=screen([0,0],camera);
  const pageEnd=pageFrame
    ?screen([pageFrame.size_um[0],pageFrame.size_um[1]],camera):null;
  const pageW=pageEnd?pageEnd.x-pageStart.x:0;
  const pageH=pageEnd?pageEnd.y-pageStart.y:0;
  const marginUm=pageFrame?.margin_um??0;
  const marginStart=pageFrame?screen([marginUm,marginUm],camera):null;
  const marginEnd=pageFrame?screen([
    pageFrame.size_um[0]-marginUm,pageFrame.size_um[1]-marginUm
  ],camera):null;
  const showMargins=marginStart&&marginEnd&&marginUm>0&&
    marginEnd.x>marginStart.x&&marginEnd.y>marginStart.y;
  // Revision forces deliberate repaint of hover / drag preview without storing any Net state.
  void revision;
  return <><svg ref={svgRef} className="gscad-drawing" role="img" tabIndex={0}
    data-testid="gscad-signed-svg-canvas" aria-label="Редактор электрической схемы, координаты в микрометрах"
    viewBox={`0 0 ${g2(size.width)} ${g2(size.height)}`}
    onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerLeave={()=>setPlacementPointer(null)}
    onPointerCancel={e=>{controller.key('Escape');if(e.currentTarget.hasPointerCapture(e.pointerId))e.currentTarget.releasePointerCapture(e.pointerId);invalidate()}}
    onWheel={e=>{setPlacementPointer(null);wheel(e)}} onContextMenu={openContextMenu}
    onKeyDown={e=>{
      // Never turn OS/browser shortcuts, held keys or IME composition into CAD edits.
      if(e.defaultPrevented||e.ctrlKey||e.metaKey||e.altKey||e.repeat||e.nativeEvent.isComposing)return;
      if(['Escape','Enter','r','R','Delete','Backspace'].includes(e.key)&&controller.key(e.key)){
        e.preventDefault();invalidate();
      }
    }}
    style={{touchAction:'none',outlineOffset:2}}>
    <defs>
      {grid&&<pattern id="cad-grid-um" width={step} height={step}
        patternUnits="userSpaceOnUse"
        patternTransform={`translate(${((camera.x%step)+step)%step} ${((camera.y%step)+step)%step})`}>
        <path d={`M ${step} 0 L 0 0 0 ${step}`} fill="none" stroke="#bbc5cb" strokeWidth={.5}/>
      </pattern>}
    </defs>
    <rect width="100%" height="100%" fill="#edf1f5"/>
    {pageFrame&&pageEnd&&<g className="cad-paper-guide" data-electrical="false"
      aria-label="Границы физического листа" pointerEvents="none">
      <rect data-testid="gscad-paper-outline"
        x={pageStart.x} y={pageStart.y} width={pageW} height={pageH}
        fill="#ffffff" stroke="#66788a" strokeWidth={1.3}/>
      {grid&&<rect data-testid="gscad-paper-grid"
        x={pageStart.x} y={pageStart.y} width={pageW} height={pageH}
        fill="url(#cad-grid-um)" stroke="none"/>}
      {showMargins&&<rect data-testid="gscad-print-margin"
        x={marginStart.x} y={marginStart.y}
        width={marginEnd.x-marginStart.x} height={marginEnd.y-marginStart.y}
        fill="none" stroke="#b6c0ca" strokeWidth={.9} strokeDasharray="5 4"/>}
      {pageW>180&&pageH>100&&<text data-testid="gscad-paper-label"
        x={pageStart.x+8} y={pageStart.y+15}
        fontSize={11} fontFamily="sans-serif" fill="#596c7e">
        {pageFrame.paper} · {pageFrame.size_um[0]/1000}×{pageFrame.size_um[1]/1000} мм
      </text>}
    </g>}
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
        data-selected={String((selectedInstanceId===s.instance_id||selectedGroup.has(s.instance_id)))}
        data-testid={'symbol-'+(document.project.components.find(c=>c.id===s.component_id)?.refdes??s.component_id)}
        stroke={(selectedInstanceId===s.instance_id||selectedGroup.has(s.instance_id))?'#e29225':undefined}>
        <SymbolInk symbol={s} camera={camera}/>
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
    {tool==='place'&&placementGuide&&<g data-testid="pin-placement-guide" data-electrical="false" pointerEvents="none">
      <line x1={screen(placementGuide.from,camera).x} y1={screen(placementGuide.from,camera).y}
        x2={screen(placementGuide.to,camera).x} y2={screen(placementGuide.to,camera).y}
        stroke="#29976a" strokeWidth={1.6} strokeDasharray="5 4"/>
      <circle cx={screen(placementGuide.to,camera).x} cy={screen(placementGuide.to,camera).y} r={4} fill="none" stroke="#29976a"/>
      <circle cx={screen(placementGuide.origin,camera).x} cy={screen(placementGuide.origin,camera).y} r={2.5} fill="#29976a"/>
      <text x={screen(placementGuide.to,camera).x+7} y={screen(placementGuide.to,camera).y-7}
        fill="#16754f" fontSize={11}>Выравнивание вывода {placementGuide.newPin}</text>
    </g>}
    {ghost&&<g data-testid="gscad-symbol-drag-preview" data-electrical="false"
      aria-label="Предпросмотр перемещения УГО" pointerEvents="none" fill="none" stroke="#d58c27"
      strokeWidth={1.8} strokeDasharray="5 3" opacity={.9}>
      <SymbolInk symbol={ghost} camera={camera}/>
    </g>}
    {groupGhosts.length>0&&<g data-testid="gscad-group-drag-preview" data-electrical="false"
      pointerEvents="none" fill="none" stroke="#d58c27" strokeWidth={1.8} strokeDasharray="5 3">
      {groupGhosts.map(s=><g key={s.instance_id}><SymbolInk symbol={s} camera={camera}/></g>)}
    </g>}
    {marquee&&<rect data-testid="gscad-selection-marquee" data-electrical="false"
      {...marquee} fill="#2c82bd" fillOpacity={.12} stroke="#2c82bd" strokeWidth={1}
      strokeDasharray="4 3" pointerEvents="none"/>}
    <g className="draft-preview" fill="none" stroke="#d58c27" strokeWidth={1.8}
      strokeDasharray="6 3" pointerEvents="none">
      {controller.preview().slice(1).map((p,i)=>{
        const prev=controller.preview()[i],a=screen(prev,camera),b=screen(p,camera);
        return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}/>;
      })}
    </g>
  </svg>
  {contextMenu&&createPortal(<div ref={menuRef} role="menu" aria-label="Контекстное меню схемы" data-testid="canvas-context-menu"
    style={{position:'fixed',left:contextMenu.x,top:contextMenu.y,zIndex:1000,width:230,maxHeight:'calc(100vh - 12px)',overflowY:'auto',padding:5,
      border:'1px solid var(--mantine-color-default-border)',borderRadius:6,background:'var(--mantine-color-body)',boxShadow:'0 4px 18px #0003'}}
    onKeyDown={e=>{
      if(!['ArrowDown','ArrowUp','Home','End'].includes(e.key))return;
      e.preventDefault();const buttons=Array.from(e.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled)'));
      if(!buttons.length)return;
      const i=buttons.indexOf(globalThis.document.activeElement as HTMLButtonElement);
      const next=e.key==='Home'?0:e.key==='End'?buttons.length-1:e.key==='ArrowDown'?(i+1)%buttons.length:(i-1+buttons.length)%buttons.length;
      buttons[next].focus();
    }}>
    {menuCommands.map(cmd=><button type="button" role="menuitem" key={cmd.key} data-testid={'context-'+cmd.key} disabled={!cmd.enabled}
      onClick={()=>runMenu(cmd.run)} style={{display:'block',width:'100%',textAlign:'left',padding:'7px 10px',border:0,borderRadius:3,background:'transparent',color:'var(--mantine-color-text)',opacity:cmd.enabled?1:.4,cursor:cmd.enabled?'pointer':'default'}}>{cmd.label}</button>)}
  </div>,globalThis.document.body)}
  </>;
}
export default CanvasViewport;
