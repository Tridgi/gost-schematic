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
const make=(tool='wire',onIntent=i=>log.push(i),scene={symbols,wires:[],junctions:[]},wireSnapshot={revision:2,wires:[]})=>{
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
 const scene={symbols:[],wires:[wire],junctions:[]};const snap={revision:27,wires:[wire]};
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
