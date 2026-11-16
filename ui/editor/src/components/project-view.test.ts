import {test} from 'node:test';
import {strict as assert} from 'node:assert';
import {projectToShellView,type ProjectViewInput} from './project-view.ts';
function fixture():ProjectViewInput{
  return {format:'gscad-project',format_version:2,project:{title:'Bench',part_definitions:[
    {id:'partA',physical_pins:[{number:'1'},{number:'2'}]},{id:'partB',physical_pins:[{number:'c'}]}
  ],components:[{id:'a:b',refdes:'R1',value:'2,3к',part_id:'partA'},{id:'a',refdes:'U1',value:'',part_id:'partB'}],nets:[
    {id:'NET0',name:'PWM',members:[{component_id:'a:b',physical_pin_number:'1'}],route_status:'unrouted'},
    {id:'NET1',name:'FB',members:[{component_id:'a',physical_pin_number:'c'}],route_status:'partial'}
  ],sheets:[{id:'s1',name:'Лист 1',instances:[
    {id:'i1',component_id:'a:b',origin_um:[-1,1001],rotation_deg:90},
    {id:'i2',component_id:'a',origin_um:[100,0],rotation_deg:0}
  ],wires:[],graphics:[{id:'b1',kind:'source_b_continuation'},{id:'b2',kind:'source_b_continuation'}]}]},workspace:{active_sheet_id:'s1'}};
}
test('physical PinRefs are distinct despite colon composite-key collision',()=>{
 const p=fixture();p.project.nets[1].members[0].physical_pin_number='b:1';
 (p.project.part_definitions[1].physical_pins as {number:string}[])[0].number='b:1';
 assert.equal(projectToShellView(p,'i1').selected?.physicalPins[0].netName,'PWM');
 assert.equal(projectToShellView(p,'i2').selected?.physicalPins[0].netName,'FB');
});
test('source graphics b never become Net or wire tree records',()=>{
 const v=projectToShellView(fixture(),'i1');
 assert.equal(v.tree.filter(x=>x.kind==='graphic').length,2);
 assert.equal(v.tree.filter(x=>x.kind==='wire').length,0);
 assert.equal(v.tree.filter(x=>x.kind==='net').length,2);
 assert.match(v.tree.find(x=>x.id==='graphic:s1:b1')!.label,/не Net/);
 assert.equal(v.tree.find(x=>x.id==='net:NET0')!.label,'PWM · unrouted');
});
test('inspector shows exact signed integer coordinates and physical pin numbers',()=>{
 const v=projectToShellView(fixture(),'i1');
 assert.deepEqual(v.selected,{id:'i1',refdes:'R1',value:'2,3к',originUm:[-1,1001],rotationDeg:90,physicalPins:[{number:'1',netName:'PWM'},{number:'2',netName:null}]});
});
test('does not mutate canonical project on tree/selection view',()=>{
 const p=fixture();const before=JSON.stringify(p);projectToShellView(p,'i2');assert.equal(JSON.stringify(p),before);
});
test('reject duplicate physical pin membership across source Nets',()=>{
 const p=fixture();(p.project.nets[1].members as {component_id:string;physical_pin_number:string}[]).push({component_id:'a:b',physical_pin_number:'1'});
 assert.throws(()=>projectToShellView(p),/DUPLICATE_PIN_MEMBERSHIP/);
});
test('reject wrong part pin on selected instance',()=>{
 const p=fixture();(p.project.nets[0].members as {component_id:string;physical_pin_number:string}[])[0].physical_pin_number='16';
 assert.throws(()=>projectToShellView(p,'i1'),/UNKNOWN_PHYSICAL_PIN/);
});
test('reject invalid selection, points, and unsupported schema',()=>{
 const p=fixture();assert.throws(()=>projectToShellView(p,'missing'),/UNKNOWN_SELECTED_INSTANCE/);
 const p2=fixture();(p2.project.sheets[0].instances[0].origin_um as unknown as number[])[0]=1.5;
 assert.throws(()=>projectToShellView(p2,'i1'),/INVALID_UM_POINT/);
 const p3=fixture();(p3 as {format_version:number}).format_version=1;
 assert.throws(()=>projectToShellView(p3),/UNSUPPORTED_PROJECT_V2/);
});
test('reject duplicate instance ids and malformed source ids',()=>{
 const p=fixture();(p.project.sheets[0].instances as any[]).push({...p.project.sheets[0].instances[0]});
 assert.throws(()=>projectToShellView(p),/DUPLICATE_INSTANCE_ID/);
 const p2=fixture();(p2.project.components as any[])[0].id='';
 assert.throws(()=>projectToShellView(p2),/INVALID_COMPONENT_ID/);
});
