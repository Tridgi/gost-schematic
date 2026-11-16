import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { ManualWireEngine, constructWire } from '../editor/src/wires/dist/manual-wire.js';

const root = resolve(fileURLToPath(new URL('../..', import.meta.url)));
const bridge = join(root,'ui/integration/project_wire_bridge.py');
const frozen = join(root,'ui/fixtures/tl494-source-e695-v2.gscad.json');
const toy = join(root,'ui/fixtures/toy-v2.gscad.json');
const python = process.env.PYTHON || 'python';
function command(...args) {
  const result=spawnSync(python,[bridge,...args],{encoding:'utf8',timeout:20000});
  assert.equal(result.status,0,result.stderr||result.error?.message||'Bridge failed');
  return result.stdout.trim();
}
function snapshot(path) {return JSON.parse(command('snapshot','--project',path));}

test('E695 imports exact 23/15/62/16, stays unrouted, b never becomes copper',()=>{
  const data=snapshot(frozen),project=JSON.parse(readFileSync(frozen,'utf8')).project;
  const da1=project.components.find(c=>c.source_refdes==='DA1');
  assert.equal(data.components.length,23);
  assert.equal(data.nets.length,15);
  assert.equal(data.nets.reduce((n,net)=>n+net.members.length,0),62);
  assert.equal(data.components.find(c=>c.id===da1.id).pins.length,16);
  assert.equal(data.wires.length,0);
  assert.equal(project.sheets[0].graphics.filter(g=>g.kind==='source_b_continuation').length,2);
  const engine=new ManualWireEngine(data);
  assert.ok(data.nets.every(n=>engine.validateNet(n.id).status==='unrouted'));
});

test('typed engine commits one physical route; Python validates saved ProjectV2 without invented Net',()=>{
  const engine=new ManualWireEngine(snapshot(frozen));
  let saved=false;
  for(const net of engine.snapshot.nets) {
    for(let i=0;i<net.members.length&&!saved;i++) {
      for(let j=i+1;j<net.members.length&&!saved;j++) {
        try {
          const a=net.members[i],b=net.members[j];
          const path=engine.previewRoute(a,b);
          engine.commitWire(engine.newTransaction('master-e695-connect'),
            constructWire('master-e695-wire',net.id,'layer-electric',path,
              {kind:'pin',...a},{kind:'pin',...b}));
          saved=true;
        }catch {/* Try a different signed physical pair: not every port normal permits a direct Manhattan path. */}
      }
    }
    if(saved)break;
  }
  assert.ok(saved,'No source-Net pin pair could be routed by the current manual engine');
  const dir=mkdtempSync(join(tmpdir(),'gscad-master-r2-'));
  try {
    const wire=join(dir,'snapshot.json'),output=join(dir,'saved.gscad.json');
    writeFileSync(wire,engine.serialize());
    const originalSha=command('digest','--project',frozen);
    command('apply','--project',frozen,'--snapshot',wire,'--expected-sha',originalSha,'--out',output);
    const initial=JSON.parse(readFileSync(frozen,'utf8')).project;
    const result=JSON.parse(readFileSync(output,'utf8')).project;
    assert.equal(result.sheets[0].wires.length,1);
    assert.deepEqual(result.nets.map(n=>[n.id,n.name,n.members]),
                     initial.nets.map(n=>[n.id,n.name,n.members]));
    assert.equal(result.nets.reduce((s,n)=>s+n.members.length,0),62);
    assert.equal(result.sheets[0].graphics.filter(g=>g.kind==='source_b_continuation').length,2);
    assert.ok(result.nets.some(n=>n.route_status==='unrouted'));
    assert.ok(result.nets.filter(n=>n.route_status==='verified').length<15);
    assert.equal(new ManualWireEngine(snapshot(output)).snapshot.wires.length,1);
  } finally {rmSync(dir,{recursive:true,force:true});}
});

test('wrong source-Net text refuses commit without writing output',()=>{
  const source=snapshot(toy);
  source.nets[0].literal_source_name='FAKE_NET';
  const dir=mkdtempSync(join(tmpdir(),'gscad-master-deny-'));
  try {
    const candidate=join(dir,'state.json'),output=join(dir,'forbidden.gscad.json');
    writeFileSync(candidate,JSON.stringify(source));
    const bad=spawnSync(python,[bridge,'apply','--project',toy,'--snapshot',candidate,
      '--expected-sha',command('digest','--project',toy),'--out',output],{encoding:'utf8'});
    assert.equal(bad.status,2);
    assert.match(bad.stderr,/SOURCE_TOPOLOGY_CHANGED/);
    assert.throws(()=>readFileSync(output));
  } finally {rmSync(dir,{recursive:true,force:true});}
});
