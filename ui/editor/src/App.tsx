import { useEffect, useMemo, useRef, useState } from 'react';
import { EditorShell, type CatalogSymbol, type DiagnosticItem, type SelectedInstance,
  type ToolMode, type TreeItem, type InspectorProposal } from './components/EditorShell';
import {worldPin as modelWorldPin,type ProjectFileV2,type SymbolDefinition} from './model/contract';
import { ManualWireEngine, WireError, constructWire, type PinRef, type PointUm,
  type WiringSnapshot } from './wires/manual-wire';
import { CanvasViewport } from './canvas/CanvasViewport';
import type { CanvasIntent } from './canvas/controller.mjs';
import { commitSegmentDrag, captureSegmentDrag } from './canvas/wire-intents.mjs';
import {noteLayout} from './model/symbol-notes.mjs';
import {curveGeometry} from './model/curves.mjs';
import {catalogDisplay,catalogAdditions} from './authoring/catalog';
import {AuthoringSession,newBlankProject,type ComponentClipboard,type GroupClipboard,type LayoutPreview} from './authoring/session';
import {nativeDesktopAvailable,nativeOpenProject,nativeSaveProject,nativeSaveAsProject,nativeCloseProject,
  nativeExportProject,type NativeDocumentHandle} from './native/desktop';
import {installNativeCloseGuard} from './native/close-guard';
import {traceNativeClose} from './native/close-trace';
import {parseProjectJsonStrict} from './authoring/strict-json';
import { loadProjectWires } from './wires/project-v2-adapter';
import { projectToCanvasScene } from './canvas/scene-projection.mjs';
import {topologyInventory} from './authoring/topology-inventory.mjs';
import {analyzeDiagnostics} from './authoring/diagnostics.mjs';
import { detectPaperOverflow } from './canvas/paper-bounds.mjs';
import { renderProjectPreviewSVG, renderPreviewPng300 } from './export/browser-export';

const umToMm = (value:number):number => value/1000;
const asPoint = (point:readonly number[]):string => String(umToMm(point[0]))+' '+String(umToMm(point[1]));
function CataloguePreview({symbol}:{symbol:SymbolDefinition}) {
  const points=[...symbol.graphics.flatMap(g=>g.kind==='circle'||g.kind==='semicircle'?curveGeometry(g.kind,g.points_um).bounds:g.points_um),...symbol.pins.map(p=>p.at_um),...(symbol.constant_annotations??[]).flatMap(n=>noteLayout(n,n.at_um).bounds),[0,0]];
  const minX=Math.min(...points.map(p=>p[0]))/1000-1,minY=Math.min(...points.map(p=>p[1]))/1000-1;
  const maxX=Math.max(...points.map(p=>p[0]))/1000+1,maxY=Math.max(...points.map(p=>p[1]))/1000+1;
  return <svg viewBox={`${minX} ${minY} ${maxX-minX} ${maxY-minY}`} fill="none" stroke="currentColor" strokeWidth={0.45}
    aria-hidden="true">
    {symbol.graphics.map((graphic,index)=>{
      const pts=graphic.points_um.map(p=>asPoint(p));
      if(graphic.kind==='circle'||graphic.kind==='semicircle'){
        const g=curveGeometry(graphic.kind,graphic.points_um),r=umToMm(g.radius);
        if(graphic.kind==='circle')return <circle key={index} cx={umToMm(g.center[0])} cy={umToMm(g.center[1])} r={r} strokeWidth={umToMm(graphic.stroke_um)}/>;
        return <path key={index} d={`M ${pts[0]} A ${r} ${r} 0 0 ${g.sweep} ${pts[2]}`} strokeWidth={umToMm(graphic.stroke_um)}/>;
      }
      if(graphic.kind==='rect'){
        const a=graphic.points_um[0],b=graphic.points_um[1];
        return <rect key={index} x={umToMm(Math.min(a[0],b[0]))}
          y={umToMm(Math.min(a[1],b[1]))} width={umToMm(Math.abs(a[0]-b[0]))}
          height={umToMm(Math.abs(a[1]-b[1]))} strokeWidth={umToMm(graphic.stroke_um)}/>;
      }
      return <polyline key={index} points={pts.join(' ')} strokeWidth={umToMm(graphic.stroke_um)} />;
    })}
    {(symbol.constant_annotations??[]).map(n=>{const l=noteLayout(n,n.at_um);return <text key={n.key} x={umToMm(l.baseline[0])} y={umToMm(l.baseline[1])} textAnchor={l.anchor} fontSize={umToMm(n.height_um)} fill="currentColor" stroke="none">{n.text}</text>})}
  </svg>;
}

/** Render two detached models with one common physical viewBox.
 * Images are SVG image resources, never executable markup in the editor. */
function layoutComparisonImages(before:ProjectFileV2,after:ProjectFileV2):{beforeSrc:string;afterSrc:string}{
  const sheetId=before.workspace.active_sheet_id;
  let x0=Infinity,y0=Infinity,x1=-Infinity,y1=-Infinity;
  const include=(p:readonly number[],pad=0)=>{
    x0=Math.min(x0,p[0]-pad);y0=Math.min(y0,p[1]-pad);x1=Math.max(x1,p[0]+pad);y1=Math.max(y1,p[1]+pad);
  };
  for(const file of [before,after]){
    const sh=file.project.sheets.find(s=>s.id===sheetId)!;
    const defs=new Map(file.project.symbol_definitions.map(d=>[d.id,d]));
    for(const inst of sh.instances){
      const d=defs.get(inst.symbol_id);if(!d)continue;
      include(inst.origin_um);
      for(const p of d.pins)include(modelWorldPin(inst,p.at_um));
      for(const g of d.graphics){
        const points=g.kind==='circle'||g.kind==='semicircle'?curveGeometry(g.kind,g.points_um).bounds:g.points_um;
        for(const p of points)include(modelWorldPin(inst,p),g.stroke_um/2);
      }
      for(const note of d.constant_annotations??[])for(const p of noteLayout(note,modelWorldPin(inst,note.at_um)).bounds)include(p);
    }
    for(const w of sh.wires)for(const v of w.vertices)include(v.at_um,150);
    for(const n of sh.junctions)include(n.at_um,550);
  }
  if(!Number.isFinite(x0)){x0=0;y0=0;x1=420000;y1=297000;}
  const cx=(x0+x1)/2,cy=(y0+y1)/2,w=Math.max(40000,x1-x0+20000),h=Math.max(40000,y1-y0+20000);
  const view=[cx-w/2,cy-h/2,w,h].map(v=>v/1000).join(' ');
  const src=(file:ProjectFileV2)=>{
    const svg=renderProjectPreviewSVG(file,sheetId).replace(/width="[^"]+" height="[^"]+" viewBox="[^"]+"/,
      'width="'+w/1000+'mm" height="'+h/1000+'mm" viewBox="'+view+'"');
    return 'data:image/svg+xml;charset=utf-8,'+encodeURIComponent(svg);
  };
  return {beforeSrc:src(before),afterSrc:src(after)};
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
  const authoringRef=useRef<AuthoringSession|null>(null);
  const frozenRef=useRef<ProjectFileV2|null>(null);
  const topologyHashRef=useRef<string|null>(null);
  const fileInputRef=useRef<HTMLInputElement|null>(null);
  const [nativeHandle,setNativeHandle]=useState<NativeDocumentHandle|null>(null);
  const [dirty,setDirty]=useState(false);
  const dirtyRef=useRef(dirty);
  dirtyRef.current=dirty;
  const nativeSaveBusyRef=useRef(false);
  // Include persisted UI settings in the edit clock; domain revisions alone miss them.
  // A separate session clock blocks late native responses from another opened project.
  const contentEpochRef=useRef(0);
  const sessionEpochRef=useRef(0);
  const [document,setDocument]=useState<ProjectFileV2|null>(null);
  const [snapshot,setSnapshot]=useState<WiringSnapshot|null>(null);
  const [tool,setTool]=useState<ToolMode>('select');
  const [placementSymbol,setPlacementSymbol]=useState<string|null>(null);
  const [selectedId,setSelectedId]=useState<string|null>(null);
  const [selectionReset,setSelectionReset]=useState(0);
  const [groupIds,setGroupIds]=useState<string[]>([]);
  const [clipboard,setClipboard]=useState<({kind:'single';template:ComponentClipboard}|{kind:'group';template:GroupClipboard})&{anchor:ComponentClipboard['origin_um']}|null>(null);
  const [,setPending]=useState<PinRef|null>(null);
  const [grid,setGrid]=useState(true),[snap,setSnap]=useState(true);
  const [smartRouting,setSmartRouting]=useState(false);
  const [pinMagnet,setPinMagnet]=useState(false);
  const [layoutPreview,setLayoutPreview]=useState<{plan:LayoutPreview;owner:AuthoringSession;sessionEpoch:number;contentEpoch:number;beforeSrc:string;afterSrc:string}|null>(null);
  const [zoom,setZoom]=useState(1);
  const [zoomRequest,setZoomRequest]=useState<{percent:50|100|200;token:number}|null>(null);
  const [fitRequest,setFitRequest]=useState(0);
  const [history,setHistory]=useState({undo:0,redo:0});
  const [issue,setIssue]=useState('R2 preview: источник E695 неразведён. Экспорт не подключён.');
  useEffect(()=>{
    if(!dirty)return;
    const guard=(event:BeforeUnloadEvent)=>{
      event.preventDefault();
      event.returnValue='';
    };
    window.addEventListener('beforeunload',guard);
    return()=>window.removeEventListener('beforeunload',guard);
  },[dirty]);
  useEffect(()=>{
    if(!nativeDesktopAvailable())return;
    traceNativeClose('app_effect_mounted',dirtyRef.current,nativeSaveBusyRef.current);
    const beforeUnload=()=>traceNativeClose('browser_beforeunload',dirtyRef.current,nativeSaveBusyRef.current);
    window.addEventListener('beforeunload',beforeUnload);
    return()=>{
      window.removeEventListener('beforeunload',beforeUnload);
      traceNativeClose('app_effect_unmounted',dirtyRef.current,nativeSaveBusyRef.current);
    };
  },[]);
  useEffect(()=>{
    let disposed=false;
    let unlisten:(()=>void)|null=null;
    void installNativeCloseGuard(
      ()=>dirtyRef.current,
      ()=>window.confirm('Есть несохранённые изменения или незавершённое сохранение. Закрыть программу?'),
      ()=>nativeSaveBusyRef.current
    ).then(off=>{
      if(disposed)off?.();else unlisten=off;
    }).catch(error=>{
      if(!disposed)setIssue('NATIVE_CLOSE_GUARD_FAILED: '+String(error));
    });
    return()=>{disposed=true;unlisten?.();};
  },[]);
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
  const activeSheet=document?.project.sheets.find(s=>s.id===document.workspace.active_sheet_id)
    ??document?.project.sheets[0];
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
    return document.project.symbol_definitions.filter(symbol=>symbol.status!=='deprecated').map(symbol=>({
      id:symbol.id,name:catalogDisplay(symbol.id)?.name??symbol.id,category:catalogDisplay(symbol.id)?.category??symbol.part_id,
      approval:symbol.status==='approved'?'approved':'draft',
      thumbnail:<CataloguePreview symbol={symbol}/>
    }));
  },[document]);
  const topology=useMemo(()=>document&&activeSheet?topologyInventory(document,activeSheet.id):undefined,[document,activeSheet?.id]);
  const diagnosticReport=useMemo(()=>{
    if(!document||!snapshot||!activeSheet)return null;
    const scene=projectToCanvasScene(document,activeSheet.id);
    const statuses=Object.fromEntries(snapshot.nets.map(n=>[n.id,engineRef.current?.validateNet(n.id).status??'unknown']));
    return analyzeDiagnostics(document,scene,snapshot,statuses);
  },[document,snapshot,activeSheet?.id]);
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
  /** Authoring commands replace the entire validated ProjectV2+WireEngine snapshot.
   * The E695 source branch retains its independent immutable topology guard.
   */
  const adoptAuthored=()=>{
    const session=authoringRef.current;if(!session)return;
    engineRef.current=session.engine;
    const next=session.file;
    setDocument(next);setSnapshot(session.snapshot);
    setSelectedId(id=>next.project.sheets.find(sh=>sh.id===next.workspace.active_sheet_id)?.instances.some(i=>i.id===id)?id:null);
    setGroupIds(ids=>{
      const visible=new Set(next.project.sheets.find(sh=>sh.id===next.workspace.active_sheet_id)?.instances.map(i=>i.id)??[]);
      const valid=ids.filter(id=>visible.has(id));return valid.length>1?valid:[];
    });
    setHistory({undo:session.canUndo?1:0,redo:session.canRedo?1:0});
    contentEpochRef.current++;
    setDirty(true);
  };
  const handleCopy=()=>{
    const a=authoringRef.current;
    if(!a||tool!=='select'||(!selectedInst&&groupIds.length<2))return;
    try{
      if(groupIds.length>1){
        const template=a.copyGroup(groupIds);
        setClipboard({kind:'group',template,anchor:[...template.anchor]});
        setIssue('Скопировано УГО: '+template.components.length+'; внутренних цепей: '+template.nets.length+'; внешних цепей исключено: '+template.omittedNetCount+'.');
        return;
      }
      if(!selectedInst)return;
      const template=a.copyComponent(selectedInst.id);
      setClipboard({kind:'single',template,anchor:[...template.origin_um]});
      setIssue('УГО скопировано во внутренний буфер. Электрические связи не копируются.');
    }catch(e){setIssue('COPY_FAILED: '+String(e));}
  };
  const handlePaste=()=>{
    const a=authoringRef.current;
    if(!a||!clipboard||!activeSheet||!document||tool!=='select')return;
    try{
      if(clipboard.kind==='group'){
        const origin=a.suggestGroupPasteOrigin(clipboard.template,clipboard.anchor,snap);
        const ids=a.pasteGroup(a.newTransaction('paste-group'),clipboard.template,origin);
        adoptAuthored();setSelectedId(null);setGroupIds(ids);
        setClipboard({...clipboard,anchor:origin});
        setIssue('Группа вставлена: '+ids.length+' УГО, '+clipboard.template.nets.length+' независимых цепей. Внешних цепей исключено: '+clipboard.template.omittedNetCount+'. Проверьте маршруты.');
        return;
      }
      const origin=a.suggestPasteOrigin(clipboard.template,clipboard.anchor,snap);
      const id=a.pasteComponent(a.newTransaction('paste-component'),clipboard.template,origin);
      adoptAuthored();setGroupIds([]);setSelectedId(id);
      setClipboard({...clipboard,anchor:origin});
      setIssue('УГО вставлено с новым обозначением и без электрических связей.');
    }catch(e){setIssue('PASTE_FAILED: '+String(e));}
  };
  const handleNew=()=>{
    if(nativeDesktopAvailable()&&nativeSaveBusyRef.current){
      setIssue('NATIVE_FILE_BUSY: завершите сохранение перед созданием проекта.');return;
    }
    if(dirty&&!window.confirm('Есть несохранённые изменения. Создать новый проект и потерять их?'))return;
    try{
      const session=new AuthoringSession(newBlankProject());
      sessionEpochRef.current++;setClipboard(null);setGroupIds([]);
      contentEpochRef.current++;
      if(nativeHandle)void nativeCloseProject(nativeHandle.handle).catch(()=>{});
      setNativeHandle(null);
      authoringRef.current=session;engineRef.current=session.engine;
      setDocument(session.file);setSnapshot(session.snapshot);
      setSelectedId(null);setPending(null);setPlacementSymbol(null);
      setTool('select');setGrid(true);setSnap(true);setDirty(false);
      setHistory({undo:0,redo:0});
      setIssue('Создан пользовательский ProjectV2 A3. Выберите УГО слева и укажите место на листе.');
    }catch(e){setIssue('NEW_PROJECT_FAILED: '+String(e));}
  };
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
    contentEpochRef.current++;
    refresh();setDirty(true);setHistory(h=>({undo:h.undo+1,redo:0}));
    setIssue('Проводник изменён через проверенную транзакцию WireEngine; исходные Nets неизменны.');
  };
  const currentProject=():ProjectFileV2=>{
    if(authoringRef.current){
      const next=authoringRef.current.file;
      next.project.settings.grid_visible=grid;
      next.project.settings.snap_enabled=snap;
      // A full re-import checks exact physical anchors and project invariants.
      new AuthoringSession(next);
      return next;
    }
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
  const activeProjectIdRef=useRef('');
  activeProjectIdRef.current=document?.project.id??'';
  const handleSave=(saveAs=false)=>{
    if(nativeDesktopAvailable()&&nativeSaveBusyRef.current){
      setIssue('NATIVE_SAVE_BUSY: дождитесь завершения файловой операции.');return;
    }
    try {
      const next=currentProject();
      if(nativeDesktopAvailable()){
        const expectedRevision=authoringRef.current?.revision??engineRef.current?.snapshot.revision??0;
        const projectId=next.project.id;
        const saveEpoch=contentEpochRef.current;
        const saveSession=sessionEpochRef.current;
        const previousHandle=nativeHandle?.handle??null;
        const action=saveAs||!nativeHandle
          ?nativeSaveAsProject(next,nativeHandle)
          :nativeSaveProject(nativeHandle,next);
        nativeSaveBusyRef.current=true;
        void action.then(result=>{
          if(activeProjectIdRef.current!==projectId||sessionEpochRef.current!==saveSession){
            void nativeCloseProject(result.handle).catch(()=>{});
            return;
          }
          setNativeHandle(result);
          // Save As publishes a new Rust session; the superseded handle must not leak.
          if(previousHandle&&previousHandle!==result.handle)
            void nativeCloseProject(previousHandle).catch(()=>{});
          const actualRevision=authoringRef.current?.revision??engineRef.current?.snapshot.revision??0;
          if(actualRevision===expectedRevision&&contentEpochRef.current===saveEpoch){
            setDirty(false);
            setIssue('NATIVE_SAVED: '+result.filename+'; Python ProjectV2 PASS, ревизия '+result.generation+'.');
          }else setIssue('SAVE_COMPLETED_BUT_DOCUMENT_CHANGED: сохраните последующие изменения отдельно.');
        }).catch(e=>setIssue('NATIVE_SAVE_FAILED: '+String(e)))
          .finally(()=>{nativeSaveBusyRef.current=false;});
        return;
      }
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
  const handleExport=async(kind:'svg'|'png300')=>{
    try {
      const next=currentProject();
      const sheet=next.project.sheets.find(s=>s.id===next.workspace.active_sheet_id);
      if(!sheet)throw Error('UNKNOWN_SHEET');
      if(nativeDesktopAvailable()){
        const filename=await nativeExportProject(next,sheet.id,kind);
        setIssue('NATIVE_PYTHON_EXPORT_PREVIEW: '+filename+
          '; физические единицы сохранены, шрифт НЕ сертифицирован по ГОСТ.');
        return;
      }
      const svg=renderProjectPreviewSVG(next,sheet.id);
      const file=kind==='svg'
        ?new Blob([svg],{type:'image/svg+xml;charset=utf-8'})
        :await renderPreviewPng300(svg,sheet.frame.size_um);
      const url=URL.createObjectURL(file);
      const anchor=window.document.createElement('a');
      anchor.href=url;anchor.download=kind==='svg'?'gost-schematic-preview.svg':'gost-schematic-preview-300dpi.png';
      window.document.body.appendChild(anchor);anchor.click();anchor.remove();
      window.setTimeout(()=>URL.revokeObjectURL(url),1000);
      setIssue('Экспорт '+kind.toUpperCase()+' готов: геометрия в мм, Nets/PinRef исходные. PREVIEW: шрифт не верифицирован по ГОСТ.');
    }catch(e){setIssue('EXPORT_FAILED: '+String(e));}
  };
  /** Import path shared by browser file picker and Rust-native selected file.
   * Synthetic projects are mutable only via AuthoringSession; frozen E695 is
   * loaded under the original source lock and cannot acquire foreign Nets.
   */
  const installValidatedProject=(next:ProjectFileV2)=>{
    if(next.format==='gscad-project'&&next.format_version===2&&
       next.project?.provenance?.status==='synthetic'){
      const author=new AuthoringSession(next);
      sessionEpochRef.current++;setClipboard(null);setGroupIds([]);contentEpochRef.current++;
      authoringRef.current=author;engineRef.current=author.engine;
      setDocument(author.file);setSnapshot(author.snapshot);
      setSelectedId(next.project.sheets.find(s=>s.id===next.workspace.active_sheet_id)?.instances[0]?.id??null);
      setGrid(next.project.settings.grid_visible);setSnap(next.project.settings.snap_enabled);
      setTool('select');setPlacementSymbol(null);setPending(null);
      setDirty(false);setHistory({undo:0,redo:0});
      setIssue('Пользовательский ProjectV2 открыт: Nets и физические PinRef прошли проверку.');
      return;
    }
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
    sessionEpochRef.current++;setClipboard(null);setGroupIds([]);contentEpochRef.current++;
    authoringRef.current=null;engineRef.current=engine;
    setDocument(next);setSnapshot(engine.snapshot);
    setSelectedId(sheet.instances[0]?.id??null);
    setGrid(next.project.settings.grid_visible);setSnap(next.project.settings.snap_enabled);
    setTool('select');setPlacementSymbol(null);setPending(null);
    setDirty(false);setHistory({undo:0,redo:0});
    setIssue('Проверенный ProjectV2 повторно открыт; PinRef и исходные Nets сохранены.');
  };
  const handleOpen=async(file:File|null)=>{
    if(!file)return;
    const pendingSession=sessionEpochRef.current;
    const pendingContent=contentEpochRef.current;
    try {
      if(file.size>8*1024*1024)throw Error('PROJECT_FILE_TOO_LARGE');
      const text=await file.text();
      if(pendingSession!==sessionEpochRef.current||pendingContent!==contentEpochRef.current)
        throw Error('OPEN_REJECTED_CHANGED_DURING_READ');
      const parsed:unknown=parseProjectJsonStrict(text);
      if(!parsed||typeof parsed!=='object')throw Error('INVALID_PROJECT_JSON');
      const next=parsed as ProjectFileV2;
      installValidatedProject(next);
      if(nativeHandle)void nativeCloseProject(nativeHandle.handle).catch(()=>{});
      setNativeHandle(null);
    }catch(e){setIssue('OPEN_FAILED: '+String(e));}
  };
  const handleOpenRequest=()=>{
    if(nativeDesktopAvailable()&&nativeSaveBusyRef.current){
      setIssue('NATIVE_FILE_BUSY: завершите сохранение перед открытием.');return;
    }
    if(dirty&&!window.confirm('Изменения не сохранены. Открыть другой файл и потерять правки?'))return;
    if(!nativeDesktopAvailable()){fileInputRef.current?.click();return;}
    const pendingSession=sessionEpochRef.current;
    const pendingContent=contentEpochRef.current;
    void nativeOpenProject().then(result=>{
      if(pendingSession!==sessionEpochRef.current||pendingContent!==contentEpochRef.current){
        void nativeCloseProject(result.handle).catch(()=>{});
        setIssue('NATIVE_OPEN_REJECTED_CHANGED_DURING_DIALOG: изменения проекта не потеряны.');
        return;
      }
      installValidatedProject(result.document);
      if(nativeHandle)void nativeCloseProject(nativeHandle.handle).catch(()=>{});
      setNativeHandle(result);
      setIssue('NATIVE_OPENED: '+result.filename+'; Python ProjectV2 PASS.');
    }).catch(e=>{
      if(String(e)!=='CANCELLED')setIssue('NATIVE_OPEN_FAILED: '+String(e));
    });
  };
  /** SVG emits typed intentions; no geometrical intersection changes electrical Nets. */
  const onCanvasIntent=(intent:CanvasIntent)=>{
    const eng=engineRef.current;if(!eng)return;
    const authored=authoringRef.current;
    if(intent.kind==='selectGroup'){
      if(intent.base_revision!==eng.snapshot.revision)return false;
      const ids=[...new Set(intent.instance_ids)];
      if(ids.length!==intent.instance_ids.length||ids.some(id=>!instances.some(i=>i.id===id)))return false;
      setGroupIds(ids.length>1?ids:[]);setSelectedId(ids.length===1?ids[0]:null);
      return true;
    }
    if(intent.kind==='moveGroup'){
      try{
        if(!authored)throw Error('SOURCE_LOCKED: групповое перемещение исходной схемы недоступно');
        if(intent.base_revision!==authored.revision)throw Error('STALE_REVISION');
        if(intent.instance_ids.length!==groupIds.length||intent.instance_ids.some(id=>!groupIds.includes(id)))throw Error('INVALID_GROUP');
        const ids=new Set(instances.filter(i=>intent.instance_ids.includes(i.id)).map(i=>i.component_id));
        const attached=authored.snapshot.wires.some(w=>[w.vertices[0],w.vertices[w.vertices.length-1]].some(
          v=>v.anchor.kind==='pin'&&ids.has(v.anchor.component_id)));
        if(attached&&!window.confirm('Переместить группу с подключёнными проводниками? Внутренние маршруты будут сдвинуты, внешние перестроены. Требуется проверка трассировки.')){
          setIssue('REROUTE_CANCELLED: перемещение группы отменено.');return false;
        }
        authored.moveGroup(authored.newTransaction('move-group'),intent.instance_ids,intent.delta_um,attached);
        adoptAuthored();setIssue(attached?'REROUTE_REVIEW_REQUIRED: группа перемещена, PinRef и Nets сохранены. Проверьте маршруты.':'Группа перемещена одной транзакцией.');return true;
      }catch(e){setIssue(e instanceof WireError?e.code+': '+e.message:String(e));return false;}
    }
    if(intent.kind==='select')setGroupIds([]);
    if(authored){
      try{
        if(intent.kind==='beginWire'){
          authored.beginWire(intent.pin);
          setPending(intent.pin);setIssue('Выбран первый физический вывод; укажите второй.');
          return true;
        }
        if(intent.kind==='cancelWire'){setPending(null);return true;}
        if(intent.kind==='select'){
          if(intent.target?.kind==='symbol')setSelectedId(intent.target.instance_id);
          else if(intent.target?.kind==='pin'){
            const selectedPin=intent.target.pin;
            const inst=instances.find(i=>i.component_id===selectedPin.component_id);
            setSelectedId(inst?.id??null);
          }else setSelectedId(null);
          return true;
        }
        if(intent.kind==='placeSymbol'){
          if(intent.base_revision!==authored.revision)throw Error('STALE_REVISION');
          if(!placementSymbol)throw Error('NO_SELECTED_CATALOG_SYMBOL');
          const hint=pinMagnet?authored.suggestAlignedPlacement(placementSymbol,intent.at_um):null;
          const id=authored.place(authored.newTransaction('place-component'),
            placementSymbol,hint?.origin??intent.at_um);
          adoptAuthored();setGroupIds([]);setSelectedId(id);
          setTool('select');setPlacementSymbol(null);
          setIssue(hint?'Выводы выровнены по одной оси. Электрическая цепь не создана.':'УГО размещено из DRAFT-каталога. Физические выводы сохранены.');
          return true;
        }
        if(intent.kind==='moveInstance'||intent.kind==='rotateInstance'){
          if(intent.base_revision!==authored.revision)throw Error('STALE_REVISION');
          const inst=instances.find(i=>i.id===intent.instance_id&&
            i.component_id===intent.component_id);
          if(!inst)throw Error('UNKNOWN_INSTANCE');
          const old=authored.snapshot.components.find(c=>c.id===intent.component_id);
          if(!old)throw Error('UNKNOWN_COMPONENT');
          const attached=authored.snapshot.wires.some(w=>
            [w.vertices[0],w.vertices[w.vertices.length-1]].some(v=>
              v.anchor.kind==='pin'&&v.anchor.component_id===intent.component_id));
          const apply=(consent:boolean)=>{
            const tx=authored.newTransaction('pointer-transform');
            if(intent.kind==='moveInstance'){
              authored.move(tx,intent.component_id,[
                old.origin_um[0]+intent.delta_um[0],
                old.origin_um[1]+intent.delta_um[1]
              ],consent);
            }else authored.rotate(tx,intent.component_id,consent);
          };
          if(attached){
            const approved=window.confirm(
              'К элементу подключены проводники. Перестроить маршруты с сохранением физических PinRef и Nets? '+
              'Все изменённые проводники будут помечены как требующие проверки трассировки.'
            );
            if(!approved){setIssue('REROUTE_CANCELLED: изменение отменено, электрическая модель не изменена.');return false;}
            apply(true);
          }else apply(false);
          adoptAuthored();
          setIssue(attached
            ?'REROUTE_REVIEW_REQUIRED: физические PinRef и Nets сохранены, проверьте новые маршруты.'
            :'Положение УГО изменено валидированной транзакцией.');
          return true;
        }
        if(intent.kind==='commitWire'){
          if(intent.target.kind!=='pin')throw Error('UNBOUND_FREE_NOT_ALLOWED');
          authored.connect(authored.newTransaction('connect-physical-pins'),
            intent.source,intent.target.pin,intent.bend_points_um,smartRouting);
          adoptAuthored();setPending(null);
          setIssue('Выводы соединены: электрический Net назначен транзакционно.');
          return true;
        }
        if(intent.kind==='moveSegment'){
          const snapshot=authored.snapshot;
          const token=intent.token;
          if(token.base_revision!==snapshot.revision||
            token.project_id!==snapshot.project_id||
            token.source_topology_hash!==snapshot.source_topology_hash)
            throw Error('STALE_REVISION');
          const current=captureSegmentDrag(snapshot,token.wire_id,token.segment_id);
          if(current.axis!==token.axis)throw Error('SEGMENT_CHANGED');
          authored.moveSegment(authored.newTransaction('drag-segment'),
            token.wire_id,token.segment_id,intent.delta_um);
          adoptAuthored();setIssue('Проводник перемещён по стабильному ID.');
          return true;
        }
        if(intent.kind==='rejectJunction'){
          setIssue(intent.reason+': нужен явно выбранный физический узел одного Net.');
          return true;
        }
        if(intent.kind==='createJunction'){
          if(intent.base_revision!==authored.revision)throw Error('STALE_REVISION');
          authored.createJunction(authored.newTransaction('explicit-junction'),
            intent.selected_segments);
          adoptAuthored();setIssue('Явный Junction построен на подтверждённом Net.');
          return true;
        }
        if(intent.kind==='deleteSymbol'){
          if(intent.base_revision!==authored.revision)throw Error('STALE_REVISION');
          const inst=instances.find(i=>i.id===intent.instance_id&&
            i.component_id===intent.component_id);
          if(!inst)throw Error('UNKNOWN_INSTANCE');
          authored.deleteComponent(authored.newTransaction('delete-component'),
            intent.component_id);
          adoptAuthored();setSelectedId(null);
          setIssue('УГО удалено транзакционно; остальные Nets не изменены.');
          return true;
        }
        if(intent.kind==='deleteWire'){
          if(intent.base_revision!==authored.revision)throw Error('STALE_REVISION');
          authored.deleteWire(authored.newTransaction('delete-wire'),intent.wire_id);
          adoptAuthored();setIssue('Проводник удалён с проверкой топологии.');
          return true;
        }
        return false;
      }catch(e){
        setIssue(e instanceof WireError?e.code+': '+e.message:String(e));
        if(intent.kind!=='commitWire')setPending(null);
        return false;
      }
    }
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
        else if(intent.target?.kind==='pin'){
          const targetPin=intent.target.pin;
          const chosen=instances.find(i=>i.component_id===targetPin.component_id);
          setSelectedId(chosen?.id??null);
        }else setSelectedId(null);
        return;
      }
      if(intent.kind==='rejectJunction'){
        setIssue(intent.reason+': выберите точное пересечение двух проводников на одном Net.');
        return true;
      }
      if(intent.kind==='createJunction'){
        const now=eng.snapshot;
        if(intent.base_revision!==now.revision)throw Error('STALE_REVISION: junction selection is stale');
        let n=now.junctions.length+1;
        while(now.junctions.some(j=>j.id==='manual-junction-'+n)||
              now.splices.some(j=>j.id==='manual-junction-'+n))n++;
        eng.connectCrossingSegmentsById(
          eng.newTransaction('create-junction-'+n),
          intent.selected_segments,'manual-junction-'+n
        );
        mutation();
        setIssue('Junction построен по подтверждённым физическим сегментам одного Net.');
        return true;
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
    }catch(e){
      setIssue(e instanceof WireError ? e.code+': '+e.message : String(e));
      // A rejected wire transaction must retain the controller's pending source PinRef,
      // allowing correction rather than falsely completing a gesture.
      if(intent.kind!=='commitWire')setPending(null);
      return false;
    }
  };
  const handleUndo=()=>{
    const author=authoringRef.current;
    if(author){if(author.undo()){adoptAuthored();setIssue('Undo: восстановлена целостная модель проекта.');}return;}
    if(engineRef.current?.undo()){
      contentEpochRef.current++;
      refresh();setDirty(true);setHistory(h=>({undo:Math.max(0,h.undo-1),redo:h.redo+1}));setIssue('Undo: отменена транзакция проводника.');}
  };
  const handleRedo=()=>{
    const author=authoringRef.current;
    if(author){if(author.redo()){adoptAuthored();setIssue('Redo: восстановлена целостная модель проекта.');}return;}
    if(engineRef.current?.redo()){
      contentEpochRef.current++;
      refresh();setDirty(true);setHistory(h=>({undo:h.undo+1,redo:Math.max(0,h.redo-1)}));setIssue('Redo: маршрут восстановлен.');}
  };
  if(!document||!snapshot||!activeSheet)return <main className="gscad-boot">
    <h1>GOST Schematic Engine — R2 preview</h1><p>{issue}</p>
    <p>Выполните Python prepare_editor_fixtures.py и npm run dev.</p></main>;
  const overflow=detectPaperOverflow(
    projectToCanvasScene(document,activeSheet.id),snapshot,activeSheet.frame.size_um);
  const diagnostics:DiagnosticItem[]=[
    {id:'integration',severity:'info',message:issue},
    ...(diagnosticReport?.items??[]),
    {id:'routed',severity:'info',message:'Проверка активного листа. Цепей в проекте: '+document.project.nets.length+'. Отсутствие замечаний не доказывает соответствие ГОСТ.'}
  ];
  if(overflow.total>0)diagnostics.push({id:'paper-overflow',severity:'warning',
    message:'За пределами физического листа: '+overflow.symbols.length+' УГО, '+
      overflow.wires.length+' проводников, '+overflow.graphics.length+' графических объектов; '+
      (overflow.junctions.length+overflow.splices.length)+' узлов. Экспорт должен быть проверен.'});
  return <EditorShell
    projectName={document.project.title+(authoringRef.current?' · R3 AUTHORING':' · R2 PREVIEW')} dirty={dirty}
    baseRevision={String(snapshot.revision)} sheets={document.project.sheets.map(s=>({id:s.id,title:s.name}))}
    activeSheetId={activeSheet.id} catalog={catalog} tree={tree} topology={topology}
    catalogMissingCount={authoringRef.current?catalogAdditions(document.project.part_definitions,document.project.symbol_definitions).length:0}
    onCatalogUpgrade={authoringRef.current?()=>{
      try{const a=authoringRef.current!;const added=a.upgradeCatalog(a.newTransaction('upgrade-catalog'));
        adoptAuthored();setIssue('Добавлено УГО: '+added+'. Существующая библиотека, PinRef и Nets сохранены.');}
      catch(e){setIssue('CATALOG_UPGRADE_FAILED: '+String(e));}
    }:undefined}
    selected={selected} groupSelectionIds={groupIds} diagnostics={diagnostics}
    diagnosticCounts={diagnosticReport?{...diagnosticReport.counts,warning:diagnosticReport.counts.warning+(overflow.total>0?1:0),info:diagnosticReport.counts.info+2}:undefined}
    clipboardSummary={clipboard?.kind==='group'?`Буфер: ${clipboard.template.components.length} УГО · ${clipboard.template.nets.length} внутренних цепей · ${clipboard.template.omittedNetCount} внешних исключено`:clipboard?.kind==='single'?'Буфер: 1 УГО без связей':undefined}
    canvas={<div className="gscad-canvas-wrapper">
      <input ref={fileInputRef} type="file" accept=".json,.gscad" data-testid="project-file-input"
        style={{display:'none'}} onChange={e=>{
          void handleOpen(e.currentTarget.files?.[0]??null);
          e.currentTarget.value='';
        }}/>
      <CanvasViewport key={sessionEpochRef.current+':'+activeSheet.id} document={document} snapshot={snapshot} sheetId={activeSheet.id}
        selectedInstanceId={selected?.id??null} selectedGroupIds={groupIds} selectionReset={selectionReset}
        tool={tool} gridVisible={grid} snapEnabled={snap}
        zoomRequest={zoomRequest??undefined} fitRequest={fitRequest}
        onIntent={onCanvasIntent} onZoomPercent={percent=>setZoom(percent/100)}
        canEdit={!!authoringRef.current}
        placementHint={pinMagnet&&tool==='place'&&placementSymbol&&authoringRef.current?at=>authoringRef.current?.suggestAlignedPlacement(placementSymbol,at)??null:undefined}
        onCopy={authoringRef.current&&(selectedInst||groupIds.length>1)&&tool==='select'?handleCopy:undefined}
        onPaste={authoringRef.current&&clipboard&&tool==='select'?handlePaste:undefined}
        onFitPage={()=>setFitRequest(n=>n+1)}/>
      {overflow.total>0&&<div data-testid="gscad-paper-warning"
        className="gscad-paper-warning" role="status">
        За пределами листа: {overflow.symbols.length} УГО, {overflow.wires.length} проводников,
        {overflow.graphics.length} графических объектов. Проверьте расположение и экспорт.
      </div>}
      {/(?:NET_CONFLICT|SOURCE_LOCKED|STALE_|UNKNOWN_|REROUTE_|MISMATCH|NOT_READY|ERROR|FAILED|DUPLICATE_|INVALID_|NO_SAFE_PASTE)/.test(issue)
        && <div className="gscad-error-banner" role="alert">{issue}</div>}
    </div>}
    tool={tool} gridVisible={grid} snapEnabled={snap} zoomPercent={Math.round(zoom*100)}
    onZoomPercent={percent=>{setZoom(percent/100);
      setZoomRequest(old=>({percent,token:(old?.token??0)+1}));}}
    onFitPage={()=>setFitRequest(n=>n+1)}
    canUndo={history.undo>0} canRedo={history.redo>0} canSave={true} exportReady={true}
    inspectorError={null}
    onToolChange={mode=>{setTool(mode);setPending(null);if(mode!=='select')setGroupIds([]);}}
    onToggleGrid={value=>{
      if(value!==grid){contentEpochRef.current++;setDirty(true);}
      setGrid(value);
    }} onToggleSnap={value=>{
      if(value!==snap){contentEpochRef.current++;setDirty(true);}
      setSnap(value);
    }}
    onPlaceSymbol={id=>{
      if(!authoringRef.current){setIssue('SOURCE_LOCKED: E695 нельзя дополнять новыми исходными PinRef.');return;}
      setGroupIds([]);setPlacementSymbol(id);setTool('place');setIssue('Кликните на листе для размещения '+id+' (DRAFT).');
    }}
    onSelectTreeItem={id=>{const i=instances.find(v=>v.id===id);
      setSelectionReset(n=>n+1);
      setGroupIds([]);setSelectedId(i?.id??null);
      if(!i)setIssue('Структура: '+id);}}
    onSelectSheet={id=>{
      const author=authoringRef.current;
      if(!author)return;
      try{author.selectSheet(author.newTransaction('switch-sheet'),id);
        adoptAuthored();setGroupIds([]);setSelectedId(null);setTool('select');
      }catch(e){setIssue('SHEET_REJECTED: '+String(e));}
    }}
    onInspectorProposal={(edit:InspectorProposal)=>{
      const eng=engineRef.current;
      try{
        const author=authoringRef.current;
        if(author){
          if(String(author.revision)!==edit.baseRevision)throw Error('STALE_REVISION');
          const inst=instances.find(i=>i.id===edit.instanceId);
          if(!inst)throw Error('UNKNOWN_INSTANCE');
          const tx=author.newTransaction('inspector-'+edit.kind);
          if(edit.kind==='propose-origin-axis'){
            const old=author.snapshot.components.find(c=>c.id===inst.component_id);
            if(!old)throw Error('UNKNOWN_COMPONENT');
            const at:[number,number]=[...old.origin_um];
            at[edit.axis==='x'?0:1]=edit.um;
            const attached=author.snapshot.wires.some(w=>
              [w.vertices[0],w.vertices[w.vertices.length-1]].some(v=>
                v.anchor.kind==='pin'&&v.anchor.component_id===inst.component_id));
            if(attached&&!window.confirm(
              'Этот элемент подключён. Перестроить проводники с сохранением Nets и PinRef? '+
              'Маршруты потребуют повторной проверки.'
            )){
              setIssue('REROUTE_CANCELLED: координаты и Nets не изменены.');
              return;
            }
            author.move(tx,inst.component_id,at,attached);
          }else if(edit.kind==='propose-refdes')
            author.updateProperty(tx,edit.instanceId,'refdes',edit.refdes);
          else author.updateProperty(tx,edit.instanceId,'value',edit.value);
          adoptAuthored();setIssue('Инспектор: изменения сохранены через CAS ProjectV2.');
          return;
        }
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
    }}
    onUndo={handleUndo} onRedo={handleRedo}
    onCopy={authoringRef.current&&(selectedInst||groupIds.length>1)&&tool==='select'?handleCopy:undefined}
    onPaste={authoringRef.current&&clipboard&&tool==='select'?handlePaste:undefined}
    smartRouting={smartRouting} onToggleSmartRouting={authoringRef.current?setSmartRouting:undefined}
    pinMagnet={pinMagnet} onTogglePinMagnet={authoringRef.current?setPinMagnet:undefined}
    layoutPreview={layoutPreview?{plan:layoutPreview.plan,beforeSrc:layoutPreview.beforeSrc,afterSrc:layoutPreview.afterSrc}:undefined}
    onCancelLayoutPreview={()=>{
      if(layoutPreview?.plan.token)layoutPreview.owner.discardLayoutPreview(layoutPreview.plan.token);
      setLayoutPreview(null);
    }}
    onApplyLayoutPreview={()=>{
      if(!layoutPreview?.plan.token)return;
      const {owner,plan,sessionEpoch,contentEpoch}=layoutPreview;
      setLayoutPreview(null);
      try{
        if(owner!==authoringRef.current||sessionEpoch!==sessionEpochRef.current||contentEpoch!==contentEpochRef.current)
          throw new WireError('STALE_REVISION','Layout preview no longer belongs to the current document');
        owner.applyLayoutPreview(owner.newTransaction('optimize-layout'),plan.token!);adoptAuthored();
        setIssue('Компоновка оптимизирована: изгибы '+plan.before.bends+' → '+plan.after.bends+'. Проверьте маршруты.');
      }catch(e){owner.discardLayoutPreview(plan.token!);setIssue('LAYOUT_OPTIMIZE_FAILED: '+String(e));}
    }}
    onOptimizeLayout={authoringRef.current&&tool==='select'?()=>{
      const a=authoringRef.current!,ids=groupIds.length>1?groupIds:[];
      try{
        const p=a.previewLayout(ids);
        if(!p.token){setIssue('Без изменений: безопасного улучшения компоновки не найдено.'+(p.limited?' Поиск ограничен.':''));return;}
        const images=layoutComparisonImages(a.file,a.layoutPreviewDocument(p.token));
        setLayoutPreview({plan:p,owner:a,sessionEpoch:sessionEpochRef.current,contentEpoch:contentEpochRef.current,...images});
      }catch(e){setIssue('LAYOUT_OPTIMIZE_FAILED: '+String(e));}
    }:undefined}
    onSimplifyRoutes={authoringRef.current&&tool==='select'?()=>{
      const a=authoringRef.current!,ids=groupIds.length>1?groupIds:[];
      if(!window.confirm(ids.length?'Упростить прямые межвыводные проводники внутри выделения?':'Упростить прямые межвыводные проводники активного листа? Положение УГО и электрические цепи не изменятся.'))return;
      try{const result=a.simplifyRoutes(a.newTransaction('simplify-routes'),ids);adoptAuthored();
        setIssue('Оптимизировано '+result.changed+' из '+result.checked+' проводников; устранено изгибов: '+result.removedBends+'; сокращено '+(result.removedLengthUm/1000).toFixed(3)+' мм. Проверьте маршруты.');}
      catch(e){setIssue(e instanceof WireError&&e.code==='NO_CHANGE'?'Без изменений: безопасного улучшения не найдено.':'ROUTE_CLEANUP_FAILED: '+String(e));}
    }:undefined}
    onDistributeParallel={authoringRef.current&&groupIds.length>=3&&tool==='select'?()=>{
      const a=authoringRef.current!;
      if(!window.confirm('Выровнять и равномерно распределить параллельные УГО, затем перестроить обе магистрали? Состав цепей сохранится.'))return;
      try{const result=a.buildParallelRails(a.newTransaction('parallel-distribution'),groupIds,true);adoptAuthored();
        setIssue('Распределены параллельные ветви: '+result.branches+', построены магистрали и явные узлы. Проверьте маршруты.');}
      catch(e){setIssue(e instanceof WireError&&e.code==='NO_CHANGE'?'Параллельные ветви уже распределены.':'PARALLEL_LAYOUT_FAILED: '+String(e));}
    }:undefined}
    onBuildParallelRails={authoringRef.current&&groupIds.length>=3&&tool==='select'?()=>{
      const a=authoringRef.current!;
      if(!window.confirm('Перестроить две замкнутые параллельные цепи в общие магистрали? УГО и состав Nets сохранятся, проводники и узлы этих двух цепей будут заменены.'))return;
      try{const result=a.buildParallelRails(a.newTransaction('parallel-rails'),groupIds);adoptAuthored();
        setIssue('Построены '+(result.axis==='horizontal'?'горизонтальные':'вертикальные')+' магистрали: ветвей '+result.branches+', проводников '+result.wires+', узлов '+result.junctions+'. Проверьте маршруты.');}
      catch(e){setIssue(e instanceof WireError&&e.code==='NO_CHANGE'?'Магистрали уже построены.':'PARALLEL_LAYOUT_FAILED: '+String(e));}
    }:undefined}
    onDistributeSeries={authoringRef.current&&groupIds.length>=3&&tool==='select'?()=>{
      const a=authoringRef.current!;
      if(!window.confirm('Выровнять цепочку и сделать одинаковыми промежутки между физическими выводами? Продольные координаты крайних УГО сохранятся.'))return;
      try{const result=a.alignSeries(a.newTransaction('distribute-series'),groupIds,true);adoptAuthored();
        setIssue('Цепочка распределена по равным межвыводным промежуткам: перемещено УГО '+result.moved+', изменено проводников '+result.wires+'. Проверьте маршруты.');}
      catch(e){setIssue(e instanceof WireError&&e.code==='NO_CHANGE'?'Цепочка уже распределена.':'SERIES_SPACING_FAILED: '+String(e));}
    }:undefined}
    onAlignSeries={authoringRef.current&&groupIds.length>=3&&tool==='select'?()=>{
      const a=authoringRef.current!;
      if(!window.confirm('Выровнять выделенную последовательную цепочку по физическим выводам? Внешние соединения и закреплённые УГО останутся на месте.'))return;
      try{const result=a.alignSeries(a.newTransaction('align-series'),groupIds);adoptAuthored();
        setIssue('Цепочка выровнена '+(result.axis==='horizontal'?'горизонтально':'вертикально')+': перемещено УГО '+result.moved+', перестроено проводников '+result.wires+', устранено изгибов '+result.removedBends+'. Проверьте маршруты.');}
      catch(e){setIssue(e instanceof WireError&&e.code==='NO_CHANGE'?'Цепочка уже выровнена.':'SERIES_ALIGN_FAILED: '+String(e));}
    }:undefined}
    onAlignConnectedPair={authoringRef.current&&groupIds.length===2&&tool==='select'?()=>{
      const a=authoringRef.current!;
      if(!window.confirm('Выровнять соединённые физические выводы, переместив один из двух элементов? Остальные связи сохраняются.'))return;
      try{const result=a.alignConnectedPair(a.newTransaction('align-connected-pair'),groupIds);adoptAuthored();
        setIssue('Выводы выровнены: '+result.beforeBends+' изгибов → 0. Проверьте маршрут.');}
      catch(e){setIssue('ALIGN_FAILED: '+String(e));}
    }:undefined}
    onNew={handleNew}
    activePaper={activeSheet.frame.paper.split(' ')[0] as 'A4'|'A3'|'A2'}
    onPaperChange={authoringRef.current?paper=>{
      try{
        const a=authoringRef.current!;
        a.setPaper(a.newTransaction('set-paper-'+paper),paper);
        adoptAuthored();
        setIssue('Формат активного листа: '+paper+' (альбомный). Геометрия Nets и PinRef сохранена.');
      }catch(e){setIssue('PAPER_CHANGE_REJECTED: '+String(e));}
    }:undefined}
    onAddSheet={authoringRef.current?()=>{
      try{const a=authoringRef.current!;a.addSheet(a.newTransaction('add-sheet'));
        adoptAuthored();setIssue('Добавлен новый лист A3.');}
      catch(e){setIssue('ADD_SHEET_FAILED: '+String(e));}
    }:undefined}
    onOpen={handleOpenRequest} onSave={()=>handleSave(false)}
    onSaveAs={()=>handleSave(true)}
    onExport={format=>{void handleExport(format)}}
  />;
}
