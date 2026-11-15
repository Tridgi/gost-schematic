// CHAT9 R1 integration-only smoke. Not a substitute for #122 schema or #123 WireEngine.
export const SOURCE_SHA="e695c415fdced164b0e0c39c5249d030795a0aa6";
function deny(code){throw Error(code)}
const point=p=>Array.isArray(p)&&p.length===2&&p.every(n=>Number.isSafeInteger(n)&&Math.abs(n)<=1e9);
const same=(a,b)=>a[0]===b[0]&&a[1]===b[1];
const key=p=>p.component_id+":"+p.physical_pin_number;
export function auditCandidateV2(file,{pinWorld,requireFrozen=false}={}){
 if(file?.format!=="gscad-project"||file.format_version!==2||!file.project)deny("UNSUPPORTED_SCHEMA");
 const p=file.project;
 if(!["components","nets","sheets"].every(k=>Array.isArray(p[k])))deny("MISSING_COLLECTION");
 if(!p.sheets.length)deny("EMPTY_PROJECT");
 const components=new Set(p.components.map(x=>x.id));
 if(components.has(undefined)||components.size!==p.components.length)deny("DUPLICATE_COMPONENT");
 const ownership=new Map(),netIds=new Set();
 for(const net of p.nets){
  if(!net?.id||netIds.has(net.id)||!Array.isArray(net.members)||!net.members.length)deny("INVALID_NET");
  netIds.add(net.id);
  for(const pin of net.members){
   if(!components.has(pin?.component_id)||typeof pin.physical_pin_number!=="string")deny("INVALID_PINREF");
   if(ownership.has(key(pin)))deny("DUPLICATE_PIN_OWNERSHIP");
   ownership.set(key(pin),net.id);
  }
 }
 const sheetIds=new Set(),freeIds=new Set();let wireCount=0,graphicCount=0;
 for(const sh of p.sheets){
  if(!sh?.id||sheetIds.has(sh.id))deny("DUPLICATE_SHEET");sheetIds.add(sh.id);
  if(!["wires","junctions","graphics","instances"].every(k=>Array.isArray(sh[k])))deny("INVALID_SHEET");
  if(sh.splices!==undefined&&!Array.isArray(sh.splices))deny("INVALID_SPLICES");
  const junctions=new Map(sh.junctions.map(x=>[x.id,x])),splices=new Map((sh.splices||[]).map(x=>[x.id,x]));
  if(junctions.size!==sh.junctions.length||splices.size!==(sh.splices||[]).length||[...junctions.keys()].some(k=>splices.has(k)))deny("DUPLICATE_JUNCTION");
  const usage=new Map(),wireIds=new Set();
  for(const w of sh.wires){
   if(!w?.id||wireIds.has(w.id)||!netIds.has(w.net_id)||w.mode!=="orthogonal"||typeof w.layer_id!=="string"||!w.layer_id||!Array.isArray(w.vertices)||w.vertices.length<2||!Array.isArray(w.segments)||w.segments.length!==w.vertices.length-1)deny("INVALID_WIRE");
   wireIds.add(w.id);
   const vertices=new Set(),segments=new Set();
   for(let i=0;i<w.vertices.length;i++){
    const v=w.vertices[i],a=v?.anchor;
    if(!v?.id||vertices.has(v.id)||!point(v.at_um))deny("INVALID_VERTEX");vertices.add(v.id);
    if(i){const q=w.vertices[i-1].at_um;if(same(q,v.at_um)||(q[0]!==v.at_um[0]&&q[1]!==v.at_um[1]))deny("NON_ORTHOGONAL");}
    if(!a||!["pin","junction","splice","free","bend"].includes(a.kind))deny("INVALID_ANCHOR");
    if((i===0||i===w.vertices.length-1)?a.kind==="bend":a.kind!=="bend")deny("INVALID_VERTEX_ANCHOR");
    if(a.kind==="pin"){
     if(ownership.get(key(a))!==w.net_id)deny("PIN_NET_MISMATCH");
     if(pinWorld){const q=pinWorld(a,p,sh);if(!point(q)||!same(q,v.at_um))deny("PIN_DRIFT");}
    }else if(a.kind==="junction"||a.kind==="splice"){
     const id=a.kind==="junction"?a.junction_id:a.splice_id;
     const record=(a.kind==="junction"?junctions:splices).get(id);
     if(!record||record.net_id!==w.net_id||!point(record.at_um)||!same(record.at_um,v.at_um))deny("ANCHOR_MISMATCH");
     const token=a.kind+":"+id;usage.set(token,(usage.get(token)||0)+1);
    }else if(a.kind==="free"){
     if(!a.free_id||freeIds.has(a.free_id))deny("FREE_ENDPOINT_ID");freeIds.add(a.free_id);
    }
   }
   for(let i=0;i<w.segments.length;i++){
    const e=w.segments[i];if(!e?.id||segments.has(e.id)||e.from_vertex_id!==w.vertices[i].id||e.to_vertex_id!==w.vertices[i+1].id)deny("SEGMENT_MISMATCH");
    segments.add(e.id);
   }
  }
  for(const j of sh.junctions)if(!point(j.at_um)||!netIds.has(j.net_id)||(usage.get("junction:"+j.id)||0)<2)deny("ORPHAN_JUNCTION");
  for(const j of sh.splices||[])if(!point(j.at_um)||!netIds.has(j.net_id)||(usage.get("splice:"+j.id)||0)!==2)deny("INVALID_SPLICE");
  if(sh.graphics.some(g=>g.kind==="source_b_continuation"&&g.electrical===true))deny("NON_ELECTRICAL_GRAPHIC");
  wireCount+=sh.wires.length;graphicCount+=sh.graphics.length;
 }
 const counts={components:components.size,nets:netIds.size,memberships:ownership.size,wires:wireCount,graphics:graphicCount};
 if(requireFrozen){
  if(p.provenance?.source_sha!==SOURCE_SHA)deny("FROZEN_SHA_MISMATCH");
  if(components.size!==23||netIds.size!==15||ownership.size!==62)deny("FROZEN_COUNTS_MISMATCH");
  const da=p.components.find(c=>c.source_refdes==="DA1");
  if(!da||[...ownership.keys()].filter(k=>k.startsWith(da.id+":")).length!==16)deny("FROZEN_DA1_MISMATCH");
  if(p.sheets.flatMap(s=>s.graphics.filter(g=>g.kind==="source_b_continuation")).length!==2)deny("FROZEN_B_MISMATCH");
  if(p.nets.some(n=>n.route_status==="verified"))deny("UNVERIFIED_ROUTING");
 }
 return {status:"STRUCTURAL_ONLY",counts}; // NOT manufacturer/ERC/GOST approval
}
