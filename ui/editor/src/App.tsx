import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react';
import { EditorShell, type CatalogSymbol, type DiagnosticItem, type SelectedInstance,
  type ToolMode, type TreeItem, type InspectorProposal } from './components/EditorShell';
import type { ProjectFileV2, SymbolDefinition } from './model/contract';
import { ManualWireEngine, constructWire, type PinRef, type WirePolyline,
  type WiringSnapshot } from './wires/manual-wire';
import { projectToCanvasScene } from './canvas/scene-projection.mjs';
import { pinWorld } from './canvas/precision.mjs';

const umToMm = (value:number):number => value/1000;
const asPoint = (point:readonly number[]):string => String(umToMm(point[0]))+' '+String(umToMm(point[1]));
type SceneSymbol = {instance_id:string;component_id:string;origin_um:[number,number];
  rotation_deg:number;mirror_x:boolean; pins:{physical_pin_number:string;at_um:[number,number];normal:string}[];
  strokes:{from_um:[number,number];to_um:[number,number]}[]; status:string};
type Scene = {symbols:SceneSymbol[];graphics:{
  id:string;source_role:string;strokes:{from_um:[number,number];to_um:[number,number]}[]
}[]};
type CanvasProps = {
  document:ProjectFileV2;snapshot:WiringSnapshot;sheetId:string;tool:ToolMode;
  grid:boolean;snap:boolean;zoom:number;pending:PinRef|null;
  selectedId:string|null;onPickPin:(pin:PinRef)=>void;
  onMoveSegment:(wireId:string,segment:number,deltaUm:number)=>void;
  onSelectInstance:(id:string)=>void;onZoom:(value:number)=>void;
};

function CataloguePreview({symbol}:{symbol:SymbolDefinition}) {
  return <svg viewBox="-12 -8 24 16" fill="none" stroke="currentColor" strokeWidth={0.45}
    aria-hidden="true">
    {symbol.graphics.map((graphic,index)=>{
      const pts=graphic.points_um.map(p=>asPoint(p));
      if(graphic.kind==='rect'){
        const a=graphic.points_um[0],b=graphic.points_um[1];
        return <rect key={index} x={umToMm(Math.min(a[0],b[0]))}
          y={umToMm(Math.min(a[1],b[1]))} width={umToMm(Math.abs(a[0]-b[0]))}
          height={umToMm(Math.abs(a[1]-b[1]))}/>;
      }
      return <polyline key={index} points={pts.join(' ')} />;
    })}
  </svg>;
}

function SchematicCanvas(props:CanvasProps) {
  const svg=useRef<SVGSVGElement>(null);
  const drag=useRef<{wire:string;index:number;start:[number,number];axis:'x'|'y'}|null>(null);
  const sheet=props.document.project.sheets.find(s=>s.id===props.sheetId);
  if(!sheet)throw Error('UNKNOWN_SHEET');
  const scene=projectToCanvasScene(props.document,props.sheetId) as unknown as Scene;
  const comps=new Map(props.document.project.components.map(c=>[c.id,c]));
  const viewWidth=420/props.zoom,viewHeight=297/props.zoom;
  const viewBox=[(420-viewWidth)/2,(297-viewHeight)/2,viewWidth,viewHeight].join(' ');
  const toUm=(event:ReactPointerEvent<SVGElement>):[number,number]|null=>{
    const el=svg.current,ctm=el?.getScreenCTM();
    if(!el||!ctm)return null;
    const point=el.createSVGPoint();
    point.x=event.clientX;point.y=event.clientY;
    const actual=point.matrixTransform(ctm.inverse());
    return [Math.round(actual.x*1000),Math.round(actual.y*1000)];
  };
  const beginDrag=(e:ReactPointerEvent<SVGLineElement>,w:WirePolyline,i:number)=>{
    if(props.tool!=='select'||i===0||i===w.segments.length-1)return;
    const pos=toUm(e);if(!pos)return;
    e.preventDefault();e.stopPropagation();e.currentTarget.setPointerCapture(e.pointerId);
    const a=w.vertices[i].at_um,b=w.vertices[i+1].at_um;
    drag.current={wire:w.id,index:i,start:pos,axis:a[0]===b[0]?'x':'y'};
  };
  const endDrag=(e:ReactPointerEvent<SVGLineElement>)=>{
    const d=drag.current;drag.current=null;if(!d)return;
    const pos=toUm(e);if(!pos)return;
    const raw=d.axis==='x'?pos[0]-d.start[0]:pos[1]-d.start[1];
    const grid=props.document.project.settings.grid_step_um;
    const delta=props.snap?Math.round(raw/grid)*grid:raw;
    if(delta!==0)props.onMoveSegment(d.wire,d.index,delta);
    if(e.currentTarget.hasPointerCapture(e.pointerId))e.currentTarget.releasePointerCapture(e.pointerId);
  };
  return <svg ref={svg} className="gscad-drawing" data-testid="gscad-real-v2-canvas"
    viewBox={viewBox} role="img" aria-label="Черновая электрическая схема, миллиметры"
    onWheel={e=>props.onZoom(Math.min(4,Math.max(0.5,props.zoom*(e.deltaY<0?1.1:0.9))))}>
    <defs><pattern id="v2-grid" width={umToMm(props.document.project.settings.grid_step_um)}
      height={umToMm(props.document.project.settings.grid_step_um)} patternUnits="userSpaceOnUse">
      <path d={'M '+umToMm(props.document.project.settings.grid_step_um)+' 0 L 0 0 0 '+
        umToMm(props.document.project.settings.grid_step_um)}
        stroke="#b9c8d4" strokeWidth={0.06} fill="none"/>
    </pattern></defs>
    <rect x={0} y={0} width={420} height={297} fill="#fff"/>
    {props.grid&&<rect x={0} y={0} width={420} height={297} fill="url(#v2-grid)"/>}
    {scene.graphics.map(g=><g key={g.id} data-electrical="false" data-source-role={g.source_role}>
      {g.strokes.map((line,i)=><line key={i} x1={umToMm(line.from_um[0])} y1={umToMm(line.from_um[1])}
        x2={umToMm(line.to_um[0])} y2={umToMm(line.to_um[1])}
        stroke="#a15c27" strokeWidth={0.3}/>)}
    </g>)}
    {scene.symbols.map(sym=>{
      const comp=comps.get(sym.component_id);
      return <g key={sym.instance_id} data-component-id={sym.component_id}
        data-testid={'symbol-'+(comp?.refdes??sym.component_id)}>
        <g transform={'translate('+asPoint(sym.origin_um)+') rotate('+sym.rotation_deg+
          ') scale('+(sym.mirror_x?-1:1)+' 1)'}>
          {sym.strokes.map((l,i)=><line key={i} x1={umToMm(l.from_um[0])} y1={umToMm(l.from_um[1])}
            x2={umToMm(l.to_um[0])} y2={umToMm(l.to_um[1])}
            stroke="#192d3b" strokeWidth={0.3} fill="none"/>)}
        </g>
        <text x={umToMm(sym.origin_um[0])} y={umToMm(sym.origin_um[1]-7000)}
          textAnchor="middle" fontSize={2.7} fill="#1c344b"
          onClick={()=>props.onSelectInstance(sym.instance_id)}
          style={{cursor:'pointer',fontWeight:props.selectedId===sym.instance_id?700:400}}>
          {comp?.refdes??sym.component_id}
        </text>
      </g>;
    })}
    {props.snapshot.wires.map(w=><g key={w.id} data-net-id={w.net_id}>
      {w.segments.map((segment,i)=>{
        const a=w.vertices.find(v=>v.id===segment.from_vertex_id);
        const b=w.vertices.find(v=>v.id===segment.to_vertex_id);
        if(!a||!b)return null;
        const line={x1:umToMm(a.at_um[0]),y1:umToMm(a.at_um[1]),
          x2:umToMm(b.at_um[0]),y2:umToMm(b.at_um[1])};
        const movable=i>0&&i<w.segments.length-1;
        return <g key={segment.id}>
          <line {...line} stroke="#182738" strokeWidth={0.3}/>
          {props.tool==='select'&&<line {...line} stroke="transparent" strokeWidth={3}
            data-testid={'segment-'+segment.id} data-movable={String(movable)}
            style={{cursor:movable?'move':'default',touchAction:'none'}}
            onPointerDown={e=>beginDrag(e,w,i)}
            onPointerUp={endDrag}
            onPointerCancel={()=>{drag.current=null;}}/>}
        </g>;
      })}
    </g>)}
    {props.snapshot.junctions.map(j=><circle key={j.id} cx={umToMm(j.at_um[0])}
      cy={umToMm(j.at_um[1])} r={0.65} fill="#192d3b" data-junction={j.id}/>)}
    {props.tool==='wire'&&scene.symbols.flatMap(sym=>sym.pins.map(pin=>{
      const found=pinWorld(sym,pin.physical_pin_number);
      const ref:PinRef={component_id:sym.component_id,physical_pin_number:pin.physical_pin_number};
      const isPending=props.pending?.component_id===ref.component_id&&
        props.pending.physical_pin_number===ref.physical_pin_number;
      return <circle key={sym.instance_id+':'+pin.physical_pin_number}
        data-testid={'pin-'+sym.component_id+'-'+pin.physical_pin_number}
        cx={umToMm(found.at_um[0])} cy={umToMm(found.at_um[1])}
        r={1.6} fill={isPending?'#e69b37':'#1985ba'} stroke="#fff" strokeWidth={0.3}
        style={{cursor:'crosshair'}} onPointerDown={e=>e.stopPropagation()}
        onClick={e=>{e.stopPropagation();props.onPickPin(ref);}}/>;
    }))}
    <text x={8} y={288} fontSize={2.8} fill="#94612c">
      DRAFT — исходные Nets сохранены; маршрутизация может быть неполной
    </text>
  </svg>;
}

export default function App() {
  const engineRef=useRef<ManualWireEngine|null>(null);
  const [document,setDocument]=useState<ProjectFileV2|null>(null);
  const [snapshot,setSnapshot]=useState<WiringSnapshot|null>(null);
  const [tool,setTool]=useState<ToolMode>('select');
  const [selectedId,setSelectedId]=useState<string|null>(null);
  const [pending,setPending]=useState<PinRef|null>(null);
  const [grid,setGrid]=useState(true),[snap,setSnap]=useState(true);
  const [zoom,setZoom]=useState(1);
  const [history,setHistory]=useState({undo:0,redo:0});
  const [issue,setIssue]=useState('R2 preview: источник E695 неразведён. Экспорт не подключён.');
  useEffect(()=>{
    let alive=true;
    Promise.all([
      fetch('/fixtures/tl494-source-e695-v2.gscad.json').then(r=>{if(!r.ok)throw Error('PROJECT_HTTP_'+r.status);return r.json();}),
      fetch('/fixtures/tl494-source-e695-v2.wiring.json').then(r=>{if(!r.ok)throw Error('WIRE_HTTP_'+r.status);return r.json();})
    ]).then(([loaded,wired])=>{
      const doc=loaded as ProjectFileV2;
      if(doc.format!=='gscad-project'||doc.format_version!==2)throw Error('FORMAT_V2_REQUIRED');
      const engine=new ManualWireEngine(wired as WiringSnapshot);
      if(doc.project.id!==engine.snapshot.project_id)throw Error('PROJECT_ID_MISMATCH');
      if(!alive)return;
      engineRef.current=engine;setDocument(doc);setSnapshot(engine.snapshot);
      setGrid(doc.project.settings.grid_visible);setSnap(doc.project.settings.snap_enabled);
      setSelectedId(doc.project.sheets[0]?.instances[0]?.id??null);
    }).catch(e=>{if(alive)setIssue('Ошибка загрузки канонической фикстуры: '+String(e));});
    return()=>{alive=false;engineRef.current=null;};
  },[]);
  const activeSheet=document?.project.sheets[0];
  const instances=activeSheet?.instances??[];
  const comps=document?.project.components??[];
  const compsById=new Map(comps.map(c=>[c.id,c]));
  const selectedInst=instances.find(x=>x.id===selectedId);
  const selectedComp=selectedInst?compsById.get(selectedInst.component_id):undefined;
  const selected=selectedInst&&selectedComp&&document?{
    id:selectedInst.id,refdes:selectedComp.refdes,value:selectedComp.value,
    originUm:selectedInst.origin_um,rotationDeg:selectedInst.rotation_deg,
    physicalPins:document.project.part_definitions
      .find(p=>p.id===selectedComp.part_id)?.physical_pins.map(p=>({
        number:p.number,
        netName:document.project.nets.find(n=>n.members.some(m=>
          m.component_id===selectedComp.id&&m.physical_pin_number===p.number))?.name??null
      }))??[]
  } as SelectedInstance:null;
  const catalog=useMemo<CatalogSymbol[]>(()=>{
    if(!document)return [];
    return document.project.symbol_definitions.map(symbol=>({
      id:symbol.id,name:symbol.id,category:symbol.part_id,
      approval:symbol.status==='approved'?'approved':'draft',
      thumbnail:<CataloguePreview symbol={symbol}/>
    }));
  },[document]);
  const tree=useMemo<TreeItem[]>(()=>{
    if(!document||!activeSheet)return [];
    return [
      {id:activeSheet.id,label:activeSheet.name,kind:'sheet'},
      ...instances.map(i=>({id:i.id,label:compsById.get(i.component_id)?.refdes??i.component_id,
        kind:'instance' as const,indent:1})),
      ...document.project.nets.map(n=>({id:n.id,label:n.name+' ['+n.route_status+']',
        kind:'net' as const,indent:1})),
      ...(snapshot?.wires??[]).map(w=>({id:w.id,label:'Провод '+w.id,
        kind:'wire' as const,indent:1}))
    ];
  },[document,snapshot,activeSheet,instances,compsById]);
  const refresh=()=>{const eng=engineRef.current;if(eng)setSnapshot(eng.snapshot);};
  const mutation=()=>{refresh();setHistory(h=>({undo:h.undo+1,redo:0}));setIssue('Выполнена проверяемая операция с WireEngine; сохранение ProjectV2 ожидает IPC.');};
  const handlePin=(pin:PinRef)=>{
    const eng=engineRef.current;if(!eng)return;
    try {
      const target=eng.beginWire(pin);
      if(!pending){setPending(pin);setIssue('Выбран физический PinRef; укажите второй вывод исходной Net.');return;}
      if(pin.component_id===pending.component_id&&pin.physical_pin_number===pending.physical_pin_number){
        setPending(null);return;
      }
      const start=eng.beginWire(pending);
      if(start.net_id!==target.net_id)throw Error('NET_CONFLICT: исходные Nets различны');
      const path=eng.previewRoute({kind:'pin',...pending},{kind:'pin',...pin});
      let index=eng.snapshot.wires.length+1;
      while(eng.snapshot.wires.some(w=>w.id==='manual-'+index))index++;
      const route=constructWire('manual-'+index,start.net_id,'layer-electric',path,
        {kind:'pin',...pending},{kind:'pin',...pin});
      eng.commitWire(eng.newTransaction('manual-route-'+index),route);
      setPending(null);mutation();
    } catch(e){setIssue(String(e));setPending(null);}
  };
  const handleSegment=(id:string,index:number,delta:number)=>{
    const eng=engineRef.current;if(!eng)return;
    try{eng.moveSegment(eng.newTransaction('segment-'+id),id,index,delta);mutation();}
    catch(e){setIssue(String(e));}
  };
  const handleUndo=()=>{if(engineRef.current?.undo()){
    refresh();setHistory(h=>({undo:Math.max(0,h.undo-1),redo:h.redo+1}));setIssue('Undo: изменён только визуальный маршрут.');}};
  const handleRedo=()=>{if(engineRef.current?.redo()){
    refresh();setHistory(h=>({undo:h.undo+1,redo:Math.max(0,h.redo-1)}));setIssue('Redo: маршрут восстановлен.');}};
  if(!document||!snapshot||!activeSheet)return <main className="gscad-boot">
    <h1>GOST Schematic Engine — R2 preview</h1><p>{issue}</p>
    <p>Выполните Python prepare_editor_fixtures.py и npm run dev.</p></main>;
  const diagnostics:DiagnosticItem[]=[
    {id:'integration',severity:'info',message:issue},
    {id:'routed',severity:'warning',message:'Исходных Nets: '+document.project.nets.length+
      '; сейчас без маршрута: '+snapshot.nets.filter(n=>
        engineRef.current?.validateNet(n.id).status==='unrouted').length+
      '. Отсутствие ошибок ERC не доказано.'}
  ];
  return <EditorShell
    projectName={document.project.title+' · R2 PREVIEW'} dirty={history.undo>0}
    baseRevision={snapshot.source_topology_hash} sheets={document.project.sheets.map(s=>({id:s.id,title:s.name}))}
    activeSheetId={activeSheet.id} catalog={catalog} tree={tree}
    selected={selected} diagnostics={diagnostics}
    canvas={<div className="gscad-canvas-wrapper">
      <SchematicCanvas document={document} snapshot={snapshot} sheetId={activeSheet.id}
        tool={tool} grid={grid} snap={snap} zoom={zoom} pending={pending}
        selectedId={selectedId} onPickPin={handlePin} onMoveSegment={handleSegment}
        onSelectInstance={setSelectedId} onZoom={setZoom}/>
      {/(?:NET_CONFLICT|SOURCE_LOCKED|UNKNOWN_|REROUTE_REQUIRED|MISMATCH|NOT_READY|ERROR)/.test(issue)
        && <div className="gscad-error-banner" role="alert">{issue}</div>}
    </div>}
    tool={tool} gridVisible={grid} snapEnabled={snap} zoomPercent={Math.round(zoom*100)}
    canUndo={history.undo>0} canRedo={history.redo>0} canSave={false} exportReady={false}
    inspectorError="Инспектор в R2 доступен только для чтения: требуется CAS ProjectFileV2."
    onToolChange={mode=>{setTool(mode);setPending(null);}}
    onToggleGrid={setGrid} onToggleSnap={setSnap}
    onPlaceSymbol={()=>setIssue('SOURCE_LOCKED: добавление PartDefinition требует валидированную транзакцию #122.')}
    onSelectTreeItem={id=>{const i=instances.find(v=>v.id===id);
      if(i)setSelectedId(i.id);else setIssue('Структура: '+id);}}
    onSelectSheet={()=>{}}
    onInspectorProposal={(_edit:InspectorProposal)=>setIssue('POSE_TRANSACTION_NOT_READY: запрещено обходить валидацию #122/#123.')}
    onUndo={handleUndo} onRedo={handleRedo}
    onSave={()=>setIssue('SAVE_BLOCKED: ожидается #118 Python IPC/атомарный журнал.')}
  />;
}
