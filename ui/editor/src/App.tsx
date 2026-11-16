import { useEffect, useMemo, useRef, useState } from 'react';
import { EditorShell, type CatalogSymbol, type DiagnosticItem, type SelectedInstance,
  type ToolMode, type TreeItem, type InspectorProposal } from './components/EditorShell';
import type { ProjectFileV2, SymbolDefinition } from './model/contract';
import { ManualWireEngine, constructWire, type PinRef, type PointUm,
  type WiringSnapshot } from './wires/manual-wire';
import { CanvasViewport } from './canvas/CanvasViewport';
import type { CanvasIntent } from './canvas/controller.mjs';
import { commitSegmentDrag } from './canvas/wire-intents.mjs';
import { loadProjectWires } from './wires/project-v2-adapter';
import { projectToCanvasScene } from './canvas/scene-projection.mjs';

const umToMm = (value:number):number => value/1000;
const asPoint = (point:readonly number[]):string => String(umToMm(point[0]))+' '+String(umToMm(point[1]));
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

/** Preserve signed controller bend locations; reject illegal geometry at WireEngine boundary. */
function routeThroughBends(
  start:{at_um:PointUm;normal:PointUm},
  target:{at_um:PointUm;normal:PointUm},
  bends:PointUm[]
):PointUm[] {
  const lead=(at:PointUm,normal:PointUm):PointUm=>
    [at[0]+normal[0]*3000,at[1]+normal[1]*3000];
  const points:PointUm[]=[start.at_um];
  const append=(to:PointUm)=>{
    const prev=points[points.length-1];
    if(prev[0]!==to[0]&&prev[1]!==to[1]){
      const corner:PointUm=[to[0],prev[1]];
      if(corner[0]!==prev[0]||corner[1]!==prev[1])points.push(corner);
    }
    const last=points[points.length-1];
    if(last[0]!==to[0]||last[1]!==to[1])points.push(to);
  };
  append(lead(start.at_um,start.normal));
  bends.forEach(append);
  append(lead(target.at_um,target.normal));
  append(target.at_um);
  return points;
}

/** Frozen source identity excludes mutable route_status and editor presentation. */
function sourceIdentity(file:ProjectFileV2):string {
  const p=file.project;
  return JSON.stringify({
    id:p.id,provenance:p.provenance,parts:p.part_definitions,symbols:p.symbol_definitions,
    components:p.components.map(c=>[c.id,c.source_refdes,c.part_id]),
    nets:p.nets.map(n=>[n.id,n.name,n.members])
  });
}

export default function App() {
  const engineRef=useRef<ManualWireEngine|null>(null);
  const frozenRef=useRef<ProjectFileV2|null>(null);
  const topologyHashRef=useRef<string|null>(null);
  const fileInputRef=useRef<HTMLInputElement|null>(null);
  const [dirty,setDirty]=useState(false);
  const [document,setDocument]=useState<ProjectFileV2|null>(null);
  const [snapshot,setSnapshot]=useState<WiringSnapshot|null>(null);
  const [tool,setTool]=useState<ToolMode>('select');
  const [selectedId,setSelectedId]=useState<string|null>(null);
  const [,setPending]=useState<PinRef|null>(null);
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
      frozenRef.current=structuredClone(doc);
      topologyHashRef.current=engine.snapshot.source_topology_hash;
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
  const refresh=()=>{
    const eng=engineRef.current;if(!eng)return;
    const state=eng.snapshot;
    setSnapshot(state);
    setDocument(file=>{
      if(!file)return file;
      const next=structuredClone(file);
      for(const sheet of next.project.sheets)for(const inst of sheet.instances){
        const c=state.components.find(c=>c.id===inst.component_id);
        if(c){inst.origin_um=[...c.origin_um];inst.rotation_deg=c.rotation;inst.mirror_x=c.mirror_x;}
      }
      return next;
    });
  };
  const mutation=()=>{
    refresh();setDirty(true);setHistory(h=>({undo:h.undo+1,redo:0}));
    setIssue('Проводник изменён через проверенную транзакцию WireEngine; исходные Nets неизменны.');
  };
  const currentProject=():ProjectFileV2=>{
    const eng=engineRef.current;
    if(!eng||!document||!activeSheet)throw Error('PROJECT_NOT_READY');
    const next=structuredClone(document),sheet=next.project.sheets.find(s=>s.id===activeSheet.id);
    if(!sheet)throw Error('UNKNOWN_SHEET');
    const state=eng.snapshot;
    sheet.wires=structuredClone(state.wires);
    sheet.junctions=structuredClone(state.junctions);
    sheet.splices=structuredClone(state.splices);
    next.project.settings.grid_visible=grid;
    next.project.settings.snap_enabled=snap;
    for(const net of next.project.nets)net.route_status=eng.validateNet(net.id).status;
    if(!frozenRef.current||sourceIdentity(next)!==sourceIdentity(frozenRef.current))
      throw Error('SOURCE_TOPOLOGY_MISMATCH: сохранение запрещено');
    projectToCanvasScene(next,sheet.id);
    const session=loadProjectWires(next,{
      sheet_id:sheet.id,revision:state.revision,
      source_topology_hash:state.source_topology_hash
    });
    return session.materialize(next);
  };
  const handleSave=()=>{
    try {
      const next=currentProject();
      const payload=JSON.stringify(next,null,2)+'\n';
      const url=URL.createObjectURL(new Blob([payload],{type:'application/json'}));
      const link=window.document.createElement('a');
      link.href=url;link.download='gost-schematic-project-v2.gscad.json';
      window.document.body.appendChild(link);link.click();link.remove();
      window.setTimeout(()=>URL.revokeObjectURL(url),1000);
      setDirty(false);
      setIssue('Проект v2 выгружен как редактируемый JSON; строгий Python IPC для внешних файлов ещё не подключён.');
    }catch(e){setIssue('SAVE_FAILED: '+String(e));}
  };
  const handleOpen=async(file:File|null)=>{
    if(!file)return;
    try {
      if(file.size>8*1024*1024)throw Error('PROJECT_FILE_TOO_LARGE');
      const parsed:unknown=JSON.parse(await file.text());
      if(!parsed||typeof parsed!=='object')throw Error('INVALID_PROJECT_JSON');
      const next=parsed as ProjectFileV2;
      if(next.format!=='gscad-project'||next.format_version!==2||
         !frozenRef.current||sourceIdentity(next)!==sourceIdentity(frozenRef.current))
        throw Error('SOURCE_TOPOLOGY_MISMATCH: допускается только исходный проект E695');
      const sheet=next.project.sheets[0];
      if(!sheet||next.project.sheets.length!==1)throw Error('MULTISHEET_UNSUPPORTED');
      projectToCanvasScene(next,sheet.id);
      const engine=loadProjectWires(next,{
        sheet_id:sheet.id,revision:0,
        source_topology_hash:topologyHashRef.current??''
      }).engine;
      engineRef.current=engine;
      setDocument(next);setSnapshot(engine.snapshot);
      setSelectedId(sheet.instances[0]?.id??null);
      setGrid(next.project.settings.grid_visible);
      setSnap(next.project.settings.snap_enabled);
      setDirty(false);setHistory({undo:0,redo:0});
      setIssue('Проверенный ProjectV2 повторно открыт; PinRef и исходные Nets сохранены.');
    }catch(e){setIssue('OPEN_FAILED: '+String(e));}
  };
  /** SVG emits typed intentions; no geometrical intersection changes electrical Nets. */
  const onCanvasIntent=(intent:CanvasIntent)=>{
    const eng=engineRef.current;if(!eng)return;
    try {
      if(intent.kind==='beginWire'){
        eng.beginWire(intent.pin);
        setPending(intent.pin);
        setIssue('Начат проводник от физического PinRef.');
        return;
      }
      if(intent.kind==='cancelWire'){setPending(null);return;}
      if(intent.kind==='select'){
        if(intent.target?.kind==='symbol')setSelectedId(intent.target.instance_id);
        if(intent.target?.kind==='pin'){
          const targetPin=intent.target.pin;
          const chosen=instances.find(i=>i.component_id===targetPin.component_id);
          if(chosen)setSelectedId(chosen.id);
        }
        return;
      }
      if(intent.kind==='moveInstance'||intent.kind==='rotateInstance'){
        const now=eng.snapshot;
        if(intent.base_revision!==now.revision)throw Error('STALE_REVISION: physical component changed');
        const inst=instances.find(i=>i.id===intent.instance_id&&i.component_id===intent.component_id);
        const c=now.components.find(c=>c.id===intent.component_id);
        if(!inst||!c)throw Error('UNKNOWN_COMPONENT_OR_INSTANCE');
        if(intent.kind==='moveInstance'){
          const next:[number,number]=[c.origin_um[0]+intent.delta_um[0],
            c.origin_um[1]+intent.delta_um[1]];
          eng.moveComponent(eng.newTransaction('move-instance-'+intent.instance_id),c.id,next);
        }else{
          const rotation=((c.rotation+90)%360) as 0|90|180|270;
          eng.rotateAndReanchor(eng.newTransaction('rotate-instance-'+intent.instance_id),
            c.id,rotation,false);
        }
        mutation();return;
      }
      if(intent.kind==='moveSegment'){
        commitSegmentDrag(eng,intent.token,intent.delta_um,
          'canvas-segment-'+intent.token.segment_id+'-'+eng.snapshot.revision);
        mutation();return;
      }
      if(intent.kind==='commitWire'){
        const start=eng.beginWire(intent.source);
        if(intent.target.kind!=='pin')throw Error('FREE_ENDPOINT_NOT_READY: необходим явный режим открытого конца');
        const end=eng.beginWire(intent.target.pin);
        if(start.net_id!==end.net_id)throw Error('NET_CONFLICT: контакты принадлежат разным исходным Nets');
        const points=intent.bend_points_um.length
          ?routeThroughBends(start,end,intent.bend_points_um)
          :eng.previewRoute({kind:'pin',...intent.source},{kind:'pin',...intent.target.pin});
        let index=eng.snapshot.wires.length+1;
        while(eng.snapshot.wires.some(w=>w.id==='manual-'+index))index++;
        const layer=activeSheet?.layers.find(l=>l.kind==='electrical')?.id;
        if(!layer)throw Error('MISSING_ELECTRICAL_LAYER');
        const route=constructWire('manual-'+index,start.net_id,layer,points,
          {kind:'pin',...intent.source},{kind:'pin',...intent.target.pin});
        eng.commitWire(eng.newTransaction('canvas-wire-'+index),route);
        setPending(null);mutation();
      }
    }catch(e){setIssue(String(e));setPending(null);}
  };
  const handleUndo=()=>{if(engineRef.current?.undo()){
    refresh();setDirty(true);setHistory(h=>({undo:Math.max(0,h.undo-1),redo:h.redo+1}));setIssue('Undo: отменена транзакция проводника.');}};
  const handleRedo=()=>{if(engineRef.current?.redo()){
    refresh();setDirty(true);setHistory(h=>({undo:h.undo+1,redo:Math.max(0,h.redo-1)}));setIssue('Redo: маршрут восстановлен.');}};
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
    projectName={document.project.title+' · R2 PREVIEW'} dirty={dirty}
    baseRevision={String(snapshot.revision)} sheets={document.project.sheets.map(s=>({id:s.id,title:s.name}))}
    activeSheetId={activeSheet.id} catalog={catalog} tree={tree}
    selected={selected} diagnostics={diagnostics}
    canvas={<div className="gscad-canvas-wrapper">
      <input ref={fileInputRef} type="file" accept=".json,.gscad" data-testid="project-file-input"
        style={{display:'none'}} onChange={e=>{
          void handleOpen(e.currentTarget.files?.[0]??null);
          e.currentTarget.value='';
        }}/>
      <CanvasViewport document={document} snapshot={snapshot} sheetId={activeSheet.id}
        tool={tool} gridVisible={grid} snapEnabled={snap}
        onIntent={onCanvasIntent} onZoomPercent={percent=>setZoom(percent/100)}/>
      {/(?:NET_CONFLICT|SOURCE_LOCKED|STALE_|UNKNOWN_|REROUTE_REQUIRED|MISMATCH|NOT_READY|ERROR)/.test(issue)
        && <div className="gscad-error-banner" role="alert">{issue}</div>}
    </div>}
    tool={tool} gridVisible={grid} snapEnabled={snap} zoomPercent={Math.round(zoom*100)}
    canUndo={history.undo>0} canRedo={history.redo>0} canSave={true} exportReady={false}
    inspectorError="Инспектор в R2 доступен только для чтения: требуется CAS ProjectFileV2."
    onToolChange={mode=>{setTool(mode);setPending(null);}}
    onToggleGrid={setGrid} onToggleSnap={setSnap}
    onPlaceSymbol={()=>setIssue('SOURCE_LOCKED: добавление PartDefinition требует валидированную транзакцию #122.')}
    onSelectTreeItem={id=>{const i=instances.find(v=>v.id===id);
      if(i)setSelectedId(i.id);else setIssue('Структура: '+id);}}
    onSelectSheet={()=>{}}
    onInspectorProposal={(edit:InspectorProposal)=>{
      const eng=engineRef.current;
      try{
        if(!eng)throw Error('PROJECT_NOT_READY');
        if(String(eng.snapshot.revision)!==edit.baseRevision)throw Error('STALE_REVISION');
        if(edit.kind!=='propose-origin-axis')
          throw Error('INSPECTOR_ATTRIBUTE_NOT_READY: изменение обозначений пока заблокировано');
        const instance=instances.find(i=>i.id===edit.instanceId);
        if(!instance)throw Error('UNKNOWN_INSTANCE');
        const component=eng.snapshot.components.find(c=>c.id===instance.component_id);
        if(!component)throw Error('UNKNOWN_COMPONENT');
        const next:[number,number]=[...component.origin_um];
        next[edit.axis==='x'?0:1]=edit.um;
        eng.moveComponent(eng.newTransaction('inspector-origin-'+edit.instanceId),component.id,next);
        mutation();
      }catch(e){setIssue('INSPECTOR_REJECTED: '+String(e));}
    }
    onUndo={handleUndo} onRedo={handleRedo}
    onOpen={()=>fileInputRef.current?.click()} onSave={handleSave}
  />;
}
