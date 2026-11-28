/** CI-only detached fixture, identical geometry to the source-green R63 browser test. */
import assert from 'node:assert/strict';
import {writeFileSync,mkdtempSync,rmSync} from 'node:fs';
import {resolve,join,sep} from 'node:path';
import {tmpdir} from 'node:os';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
const require=createRequire(new URL('../../ui/editor/package.json',import.meta.url));
const {build}=require('esbuild');
const root=process.env.RUNNER_TEMP,output=process.argv[2];
if(process.env.GITHUB_ACTIONS!=='true'||!root||!output||!resolve(output).toLowerCase().startsWith(resolve(root).toLowerCase()+sep))throw Error('R67_CI_PATH_INVALID');
const temp=mkdtempSync(join(tmpdir(),'r67-model-'));
try{
 const bundle=join(temp,'authoring.mjs');
 await build({entryPoints:[fileURLToPath(new URL('../../ui/editor/src/authoring/session.ts',import.meta.url))],outfile:bundle,bundle:true,platform:'node',format:'esm',target:'node22',logLevel:'silent'});
 const {AuthoringSession,newBlankProject}=await import(pathToFileURL(bundle).href);
  const s=new AuthoringSession(newBlankProject());
  const pin=(component_id,physical_pin_number)=>({component_id,physical_pin_number});
  for(const p of [[50000,80000],[200000,80000],[50000,100000],[200000,100000],[20000,60000],[250000,120000]])
   s.place(s.newTransaction('spacing-place'),'symbol/resistor.fixed',p);
  const [a,b,c,d,e,f]=s.file.project.components.map(c=>c.id);
  for(const [x,y] of [[a,b],[c,d],[e,f]])s.connect(s.newTransaction('spacing-connect'),pin(x,'2'),pin(y,'1'));
  const doc=s.file;const sh=doc.project.sheets[0];
  const set=(x,y,points,review)=>{
   const net=doc.project.nets.find(n=>n.members.some(m=>m.component_id===x));
   const w=sh.wires.find(w=>w.net_id===net.id);
   w.vertices=points.map((at_um,i)=>({id:w.id+':v'+i,at_um,anchor:i===0?{kind:'pin',...pin(x,'2')}:i===points.length-1?{kind:'pin',...pin(y,'1')}:{kind:'bend'}}));
   w.segments=w.vertices.slice(1).map((v,i)=>({id:w.id+':s'+i,from_vertex_id:w.vertices[i].id,to_vertex_id:v.id}));
   w.needs_routing_review=review;return w.id;
  };
  set(a,b,[[58000,80000],[192000,80000]],false);
  set(c,d,[[58000,100000],[192000,100000]],false);
  const middleId=set(e,f,[[28000,60000],[40000,60000],[40000,86000],[220000,86000],[220000,120000],[242000,120000]],true);
  // A real domain constructor validates the detached fixture before browser import.
  new AuthoringSession(doc);

 assert.ok(middleId);writeFileSync(output,JSON.stringify(doc),{flag:'wx'});
}finally{rmSync(temp,{recursive:true,force:true});}
