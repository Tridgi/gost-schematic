import test from 'node:test';
import assert from 'node:assert/strict';
import {createCanvasController} from './controller.mjs';
import {screen} from './precision.mjs';
const camera={s:.01,x:30,y:20};
const symbols=[
 {component_id:'R1',origin_um:[10000,10000],rotation_deg:0,mirror_x:false,pins:[{physical_pin_number:'2',at_um:[0,0],side:'right'}]},
 {component_id:'C1',origin_um:[40000,10000],rotation_deg:0,mirror_x:false,pins:[{physical_pin_number:'1',at_um:[0,0],side:'left'}]}
];
const loc=(p,button=0,pointerId=1)=>({...screen(p,camera),button,pointerId});
const make=(tool='wire',onIntent=i=>log.push(i),scene={symbols,wires:[],junctions:[]},wireSnapshot={project_id:'toy',source_topology_hash:'locked',revision:2,wires:[]})=>{
 return createCanvasController({tool,scene,wireSnapshot,camera,gridUm:1000,snapEnabled:true,onIntent});
};
let log=[];
test('start at genuine pin then another pin emits signed ids without adding Net',()=>{
 log=[];const c=make();
 assert.equal(c.down(loc([10000,10000])),true);
 assert.deepEqual(c.getState().draft.source,{component_id:'R1',physical_pin_number:'2'});
 c.move(loc([25000,20000]));
 assert.equal(c.down(loc([40000,10000])),true);
 assert.deepEqual(log.map(x=>x.kind),['beginWire','commitWire']);
 assert.deepEqual(log[1].target.pin,{component_id:'C1',physical_pin_number:'1'});
 assert.equal(c.getState().draft,null);
});
test('wrong-net commit error retains draft for correction without partial mutation',()=>{
 log=[];const c=make('wire',i=>{if(i.kind==='commitWire')throw Error('NET_CONFLICT');log.push(i)});
 c.down(loc([10000,10000]));
 assert.throws(()=>c.down(loc([40000,10000])),/NET_CONFLICT/);
 assert.equal(c.getState().draft.source.component_id,'R1');
 assert.equal(log.length,1);
});
test('wire blank click adds bend; Escape cancels without topology command',()=>{
 log=[];const c=make();c.down(loc([10000,10000]));c.move(loc([22000,17000]));c.down(loc([22000,17000]));
 assert.deepEqual(c.getState().draft.bends_um,[[22000,17000]]);
 assert.equal(c.key('Escape'),true);
 assert.deepEqual(log.map(i=>i.kind),['beginWire','cancelWire']);
 assert.equal(c.getState().draft,null);
});
test('Enter creates tagged free endpoint and snap off preserves exact µm',()=>{
 log=[];const c=make();c.down(loc([10000,10000]));
 c.setContext({snapEnabled:false});
 c.move(loc([23800,14500]));c.key('Enter');
 assert.equal(log[1].kind,'commitWire');
 assert.equal(log[1].target.kind,'free');
 assert.deepEqual(log[1].target.at_um,[23800,14500]);
});
test('interior drag emits revision-locked segment token, other pointer cannot steal',()=>{
 log=[];
 const vertices=[{id:'v0',at_um:[0,0]},{id:'v1',at_um:[7000,0]},{id:'v2',at_um:[7000,5000]},{id:'v3',at_um:[14000,5000]}];
 const wire={id:'W',net_id:'N',vertices,segments:[{id:'s0',from_vertex_id:'v0',to_vertex_id:'v1'},{id:'s1',from_vertex_id:'v1',to_vertex_id:'v2'},{id:'s2',from_vertex_id:'v2',to_vertex_id:'v3'}]};
 const scene={symbols:[],wires:[wire],junctions:[]};const snap={project_id:'toy',source_topology_hash:'locked',revision:27,wires:[wire]};
 const c=make('select',i=>log.push(i),scene,snap);
 assert.equal(c.down(loc([7000,2500])),true);
 assert.equal(c.move(loc([9000,2500],0,2)),false);
 assert.equal(c.up(loc([10000,2500],0,2)),false);
 assert.equal(c.up(loc([10000,2500])),true);
 assert.equal(log.at(-1).kind,'moveSegment');
 assert.equal(log.at(-1).token.base_revision,27);
 assert.equal(log.at(-1).token.segment_id,'s1');
 assert.equal(log.at(-1).delta_um,3000);
});
test('pan does not mutate source signed coordinates',()=>{
 log=[];const c=make('pan');c.down(loc([10000,10000]));c.move(loc([12000,11000]));c.up(loc([12000,11000]));
 assert.deepEqual(c.getState().camera,{s:.01,x:50,y:30});
 assert.equal(log.length,0);
});

test('visual symbol drag emits signed revision-locked placement intent, not a Net edit',()=>{
 log=[];
 const shape={symbols:[{
   instance_id:'S-R1',component_id:'R1',origin_um:[10000,10000],rotation_deg:0,
   mirror_x:false,pins:[],strokes:[{from_um:[-2000,-1000],to_um:[2000,-1000]}]
 }],wires:[],junctions:[]};
 const current={project_id:'toy',source_topology_hash:'locked',revision:42,wires:[]};
 const c=make('select',i=>log.push(i),shape,current);
 assert.equal(c.down(loc([10000,9000])),true);
 assert.equal(log[0].kind,'select');
 assert.equal(log[0].target.instance_id,'S-R1');
 assert.equal(c.up(loc([13000,13000])),true);
 assert.deepEqual(log.at(-1),{kind:'moveInstance',component_id:'R1',instance_id:'S-R1',
   delta_um:[3000,4000],base_revision:42});
 assert.equal(c.getState().selected.instance_id,'S-R1');
 assert.equal(c.key('r'),true);
 assert.deepEqual(log.at(-1),{kind:'rotateInstance',component_id:'R1',
   instance_id:'S-R1',base_revision:42});
});
test('ambiguous overlapping symbol ink fails closed and never begins component drag',()=>{
 log=[];
 const symbol={
   instance_id:'S-1',component_id:'C1',origin_um:[20000,30000],rotation_deg:0,
   mirror_x:false,pins:[],strokes:[{from_um:[-1000,0],to_um:[1000,0]}]
 };
 const scene={symbols:[symbol,{...symbol,instance_id:'S-2',component_id:'C2'}],wires:[],junctions:[]};
 const c=make('select',i=>log.push(i),scene,{project_id:'toy',source_topology_hash:'locked',revision:1,wires:[]});
 c.down(loc([20000,30000]));
 assert.equal(log[0].kind,'select');
 assert.equal(log[0].target.kind,'ambiguous-symbol');
 c.up(loc([25000,30000]));
 assert.equal(log.some(i=>i.kind==='moveInstance'),false);
});

test('host boolean rejection retains signed draft and permits corrected target without a new source click',()=>{
 log=[];let attempts=0;
 const c=make('wire',intent=>{
  log.push(intent);
  if(intent.kind==='commitWire'&&++attempts===1)return false;
 });
 assert.equal(c.down(loc([10000,10000])),true);
 assert.equal(c.down(loc([40000,10000])),false);
 assert.deepEqual(c.getState().draft.source,{component_id:'R1',physical_pin_number:'2'});
 assert.equal(c.down(loc([40000,10000])),true);
 assert.equal(c.getState().draft,null);
 assert.equal(log.filter(i=>i.kind==='beginWire').length,1);
 assert.equal(log.filter(i=>i.kind==='commitWire').length,2);
});
test('host rejects initial pin or free-end and no phantom connection/draft completion occurs',()=>{
 const blocked=make('wire',i=>i.kind==='beginWire'?false:true);
 assert.equal(blocked.down(loc([10000,10000])),false);
 assert.equal(blocked.getState().draft,null);
 const one=make('wire',i=>i.kind==='commitWire'?false:true);
 one.down(loc([10000,10000]));
 one.move(loc([24000,17000]));
 assert.equal(one.key('Enter'),false);
 assert.equal(one.getState().draft.source.component_id,'R1');
 assert.equal(one.key('Escape'),true);
 assert.equal(one.getState().draft,null);
});

test('explicit junction tool emits two signed segment IDs and CAS revision only on ambiguous X click',()=>{
 log=[];
 const horizontal={id:'H',net_id:'N',vertices:[{id:'h0',at_um:[0,5000]},{id:'h1',at_um:[10000,5000]}],
  segments:[{id:'hs',from_vertex_id:'h0',to_vertex_id:'h1'}]};
 const vertical={id:'V',net_id:'N',vertices:[{id:'v0',at_um:[5000,0]},{id:'v1',at_um:[5000,10000]}],
  segments:[{id:'vs',from_vertex_id:'v0',to_vertex_id:'v1'}]};
 const snap={project_id:'toy',source_topology_hash:'source',revision:71,wires:[horizontal,vertical]};
 const c=make('junction',i=>{log.push(i);return true;},
  {symbols:[],wires:[horizontal,vertical],junctions:[]},snap);
 assert.equal(c.down(loc([5000,5000])),true);
 assert.deepEqual(log[0],{kind:'createJunction',
  selected_segments:[{wire_id:'H',segment_id:'hs'},{wire_id:'V',segment_id:'vs'}],
  base_revision:71});
 assert.equal(snap.wires.length,2);
 assert.equal(snap.revision,71);
});
test('explicit junction tool on ordinary stroke refuses to invent a branch or Net',()=>{
 log=[];
 const wire={id:'H',net_id:'N',vertices:[{id:'v0',at_um:[0,5000]},{id:'v1',at_um:[10000,5000]}],
  segments:[{id:'h0',from_vertex_id:'v0',to_vertex_id:'v1'}]};
 const c=make('junction',i=>log.push(i),{symbols:[],wires:[wire],junctions:[]},
  {project_id:'toy',source_topology_hash:'source',revision:1,wires:[wire]});
 assert.equal(c.down(loc([5000,5000])),true);
 assert.deepEqual(log,[{kind:'rejectJunction',reason:'JUNCTION_SELECTION_REQUIRED'}]);
 assert.equal(c.getState().draft,null);
});

test('idle select is required for rotate/delete and successful deletion clears selection',()=>{
 const symbol={instance_id:'S-R1',component_id:'R1',origin_um:[10000,10000],
  rotation_deg:0,mirror_x:false,pins:[],strokes:[{from_um:[-2000,0],to_um:[2000,0]}]};
 const events=[];
 const c=make('select',i=>{events.push(i);return true;},
  {symbols:[symbol],wires:[],junctions:[]});
 c.down(loc([10000,10000]));
 for(const key of ['Delete','Backspace','r','R'])assert.equal(c.key(key),false);
 c.up(loc([10000,10000]));
 for(const tool of ['wire','pan','place','junction','text']){
  c.setContext({tool});
  for(const key of ['Delete','Backspace','r','R'])assert.equal(c.key(key),false);
 }
 assert.deepEqual(events.map(e=>e.kind),['select']);
 c.setContext({tool:'select'});
 assert.equal(c.key('r'),true);
 assert.equal(c.key('Delete'),true);
 assert.equal(c.getState().selected,null);
 assert.equal(c.key('Delete'),false);
 assert.deepEqual(events.map(e=>e.kind),['select','rotateInstance','deleteSymbol']);
});

test('rejected transform and deletion preserve the selected symbol',()=>{
 const symbol={instance_id:'S-R1',component_id:'R1',origin_um:[10000,10000],
  rotation_deg:0,mirror_x:false,pins:[],strokes:[{from_um:[-2000,0],to_um:[2000,0]}]};
 const c=make('select',i=>i.kind==='select',
  {symbols:[symbol],wires:[],junctions:[]});
 c.down(loc([10000,10000]));c.up(loc([10000,10000]));
 assert.equal(c.key('r'),false);
 assert.equal(c.key('Delete'),false);
 assert.equal(c.getState().selected.instance_id,'S-R1');
});

test('host selection follows tree/inspector and drops objects removed from the scene',()=>{
 const shape=id=>({instance_id:'S-'+id,component_id:id,origin_um:[10000,10000],
  rotation_deg:0,mirror_x:false,pins:[],strokes:[]});
 const a=shape('R1'),b=shape('R2');
 const scene={symbols:[a,b],wires:[],junctions:[]};
 const events=[];
 const c=make('select',i=>{events.push(i);return true;},scene);
 c.syncSymbolSelection('S-R2');
 assert.equal(c.getState().selected.component_id,'R2');
 assert.equal(c.key('r'),true);
 assert.equal(events.at(-1).component_id,'R2');
 c.setContext({scene:{...scene,symbols:[a]}});
 assert.equal(c.getState().selected,null);
 assert.equal(c.key('Delete'),false);
 c.syncSymbolSelection('S-R1');
 c.key('Escape');
 assert.equal(c.getState().selected,null);
 assert.deepEqual(events.at(-1),{kind:'select',target:null});
 c.syncSymbolSelection('S-UNKNOWN');
 assert.equal(c.getState().selected,null);
});

test('symbol drag ghost uses the same snapped delta as release and is non-mutating',()=>{
 const shape={instance_id:'S-R1',component_id:'R1',origin_um:[10000,10000],
  rotation_deg:0,mirror_x:false,pins:[],strokes:[{from_um:[-2000,0],to_um:[2000,0]}]};
 const scene={symbols:[shape],wires:[],junctions:[]};
 const snap={project_id:'toy',source_topology_hash:'locked',revision:3,wires:[]};
 const events=[];
 const c=make('select',i=>{events.push(i);return true;},scene,snap);
 c.down(loc([10000,10000]));
 assert.equal(c.symbolDragPreview(),null);
 assert.equal(c.move(loc([14500,12900],0,2)),false);
 assert.equal(c.symbolDragPreview(),null);
 c.move(loc([14500,12900]));
 assert.deepEqual(c.symbolDragPreview(),{instance_id:'S-R1',component_id:'R1',delta_um:[5000,3000]});
 assert.deepEqual(events.map(e=>e.kind),['select']);
 assert.deepEqual(scene.symbols[0].origin_um,[10000,10000]);
 c.up(loc([14500,12900]));
 assert.deepEqual(events.at(-1).delta_um,[5000,3000]);
 assert.equal(c.symbolDragPreview(),null);
});

test('Escape, tool change and stale CAS cancel ghost without moving component',()=>{
 const shape={instance_id:'S-R1',component_id:'R1',origin_um:[10000,10000],
  rotation_deg:0,mirror_x:false,pins:[],strokes:[{from_um:[-2000,0],to_um:[2000,0]}]};
 const scene={symbols:[shape],wires:[],junctions:[]};
 const snap={project_id:'toy',source_topology_hash:'locked',revision:3,wires:[]};
 const events=[];
 const c=make('select',i=>{events.push(i);return true;},scene,snap);
 const start=()=>{c.down(loc([10000,10000]));c.move(loc([15000,13000]));assert.ok(c.symbolDragPreview());};
 start();c.key('Escape');assert.equal(c.symbolDragPreview(),null);c.up(loc([15000,13000]));
 start();c.setContext({tool:'wire'});assert.equal(c.symbolDragPreview(),null);c.up(loc([15000,13000]));
 c.setContext({tool:'select'});start();
 c.setContext({wireSnapshot:{...snap,revision:4}});
 assert.equal(c.symbolDragPreview(),null);c.up(loc([15000,13000]));
 assert.ok(events.every(e=>e.kind==='select'));
});

test('R13 marquee contains entire symbol geometry and moves only selected group by a single intent',()=>{
 const shape=(id,x)=>({instance_id:'S-'+id,component_id:id,origin_um:[x,10000],
  rotation_deg:0,mirror_x:false,pins:[],strokes:[{from_um:[-2000,0],to_um:[2000,0]}]});
 const scene={symbols:[shape('R1',10000),shape('R2',20000),shape('R3',30000)],wires:[],junctions:[]};
 const events=[];
 const c=make('select',i=>{events.push(i);return true;},scene);
 c.down(loc([5000,5000]));c.move(loc([31000,15000]));
 assert.ok(c.marqueePreview());
 c.up(loc([31000,15000]));
 assert.deepEqual(c.getState().selectedGroup,['S-R1','S-R2']);
 assert.deepEqual(events.at(-1),{kind:'selectGroup',instance_ids:['S-R1','S-R2'],base_revision:2});
 assert.equal(c.key('Delete'),false);assert.equal(c.key('r'),false);
 c.down(loc([10000,10000]));c.move(loc([14300,13200]));
 assert.deepEqual(c.groupDragPreview(),{instance_ids:['S-R1','S-R2'],delta_um:[4000,3000]});
 assert.equal(events.filter(e=>e.kind==='moveGroup').length,0);
 c.up(loc([14300,13200]));
 assert.deepEqual(events.at(-1),{kind:'moveGroup',instance_ids:['S-R1','S-R2'],delta_um:[4000,3000],base_revision:2});
 assert.deepEqual(scene.symbols[0].origin_um,[10000,10000]);
 c.key('Escape');assert.deepEqual(c.getState().selectedGroup,[]);
});
test('R13 rectangle cancels on Escape/stale revision and supports one-symbol selection',()=>{
 const shape={instance_id:'S-R1',component_id:'R1',origin_um:[10000,10000],
  rotation_deg:90,mirror_x:true,pins:[{physical_pin_number:'1',at_um:[-2000,0],side:'left'}],
  strokes:[{from_um:[-1000,0],to_um:[1000,0]}]};
 const scene={symbols:[shape],wires:[],junctions:[]};
 const snap={project_id:'toy',source_topology_hash:'locked',revision:2,wires:[]};
 const events=[];
 const c=make('select',i=>{events.push(i);return true;},scene,snap);
 c.down(loc([5000,5000]));c.move(loc([15000,15000]));c.key('Escape');
 c.up(loc([15000,15000]));assert.equal(c.marqueePreview(),null);
 c.down(loc([5000,5000]));c.setContext({wireSnapshot:{...snap,revision:3}});
 c.up(loc([15000,15000]));assert.ok(events.every(e=>e.kind==='select'));
 c.down(loc([15000,15000]));c.up(loc([5000,5000]));
 assert.deepEqual(events.at(-1),{kind:'selectGroup',instance_ids:['S-R1'],base_revision:3});
 assert.equal(c.getState().selected.instance_id,'S-R1');
});

test('R16 right-click resolves one symbol or existing group without starting a drag',()=>{
 const shape=(id,x)=>({instance_id:'S-'+id,component_id:id,origin_um:[x,10000],
  rotation_deg:0,mirror_x:false,pins:[],strokes:[{from_um:[-2000,0],to_um:[2000,0]}]});
 const scene={symbols:[shape('R1',10000),shape('R2',20000)],wires:[],junctions:[]};
 const events=[],c=make('select',i=>{events.push(i);return true;},scene);
 c.syncSymbolSelection(null,false,['S-R1','S-R2']);
 assert.equal(c.contextSelect(loc([10000,10000])),'group');
 assert.equal(events.length,0);assert.equal(c.getState().drag,null);
 assert.equal(c.contextSelect(loc([40000,40000])),'blank');
 assert.deepEqual(c.getState().selectedGroup,[]);
 assert.equal(c.contextSelect(loc([20000,10000])),'symbol');
 assert.equal(c.getState().selected.instance_id,'S-R2');
 assert.ok(events.every(e=>e.kind==='select'));
 c.down(loc([20000,10000]));
 assert.equal(c.contextSelect(loc([10000,10000])),null);
 c.key('Escape');c.setContext({tool:'wire'});
 assert.equal(c.contextSelect(loc([10000,10000])),null);
});
test('R16 context target rejects ambiguous overlap instead of picking an arbitrary symbol',()=>{
 const a={instance_id:'A',component_id:'R1',origin_um:[10000,10000],rotation_deg:0,mirror_x:false,pins:[],strokes:[{from_um:[-2000,0],to_um:[2000,0]}]};
 const scene={symbols:[a,{...a,instance_id:'B',component_id:'R2'}],wires:[],junctions:[]};
 const events=[],c=make('select',i=>{events.push(i);return true;},scene);
 assert.equal(c.contextSelect(loc([10000,10000])),null);
 assert.equal(c.getState().selected,null);assert.deepEqual(events,[]);
});


test('RC1 pointer snaps only along selected segment and rejects stale wire drafts',()=>{
 const w={id:'W',net_id:'N',vertices:[{id:'a',at_um:[20000,20000]},{id:'b',at_um:[50000,20000]}],segments:[{id:'s',from_vertex_id:'a',to_vertex_id:'b'}]};
 const scene={symbols,wires:[w],junctions:[]},snapshot={project_id:'toy',source_topology_hash:'locked',revision:2,wires:[w]};
 const events=[],c=make('wire',i=>{events.push(i);return true;},scene,snapshot);
 c.setContext({canTap:true});c.down(loc([10000,10000]));
 c.move(loc([30300,20300]));
 assert.deepEqual(c.tapPreview(),{kind:'segment',wire_id:'W',segment_id:'s',at_um:[30000,20000]});
 c.down(loc([30300,20300]));
 assert.equal(events.at(-1).kind,'commitWire');assert.deepEqual(events.at(-1).target.at_um,[30000,20000]);
 assert.equal(c.tapPreview(),null);
 c.down(loc([10000,10000]));c.setContext({wireSnapshot:{...snapshot,revision:3}});
 assert.equal(c.getState().draft,null);
});
test('RC1 Ctrl and Shift click toggle selection without starting a drag',()=>{
 const shape=(id,x)=>({instance_id:'S-'+id,component_id:id,origin_um:[x,10000],rotation_deg:0,mirror_x:false,pins:[],strokes:[{from_um:[-2000,0],to_um:[2000,0]}]});
 const scene={symbols:[shape('R1',10000),shape('R2',20000)],wires:[],junctions:[]},events=[];
 const c=make('select',i=>{events.push(i);return true;},scene);
 c.down(loc([10000,10000]));c.up(loc([10000,10000]));
 c.down({...loc([20000,10000]),ctrlKey:true});
 assert.deepEqual(c.getState().selectedGroup,['S-R1','S-R2']);assert.equal(c.getState().drag,null);
 c.down({...loc([10000,10000]),shiftKey:true});
 assert.equal(c.getState().selected.instance_id,'S-R2');assert.deepEqual(c.getState().selectedGroup,[]);
});
