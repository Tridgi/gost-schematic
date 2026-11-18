// GOST Visual CAD R0 independent evaluation prototype. Coordinate domain: integer micrometres.
// This is intentionally NOT the strict gse-project v1 format.
export const FORMAT = 'gscad-spike';
export const VERSION = 1;
export const UM = 1000;
export const LIBRARY = Object.freeze({
  'resistor.fixed': { label: 'Резистор', refPrefix: 'R', pins: [
    { number: '1', x: -8000, y: 0 }, { number: '2', x: 8000, y: 0 }
  ] },
  'capacitor.fixed': { label: 'Конденсатор', refPrefix: 'C', pins: [
    { number: '1', x: -8000, y: 0 }, { number: '2', x: 8000, y: 0 }
  ] },
  'ic.tl494.demo': { label: 'TL494 (демо)', refPrefix: 'DA', pins: [
    ...Array.from({ length: 8 }, (_, i) => ({ number: String(i + 1), x: -22000, y: -17500 + i * 5000 })),
    ...Array.from({ length: 8 }, (_, i) => ({ number: String(i + 9), x: 22000, y: 17500 - i * 5000 }))
  ] }
});
export const deep = value => structuredClone(value);
export function uid(prefix='id') { return `${prefix}-${Math.random().toString(36).slice(2,10)}`; }
export function demo() {
  return { format: FORMAT, version: VERSION, projectId: uid('project'), title: 'Новый проект',
    provenance: { kind: 'synthetic-demo', note: 'TL494 synthetic graphic, NOT source verified or ESKD-approved; R/C source DRAFT', catalogSources: {
      'resistor.fixed': 'integration/stage0-12:4114cecde344ce184b8271851141c254cfa9f7aa',
      'capacitor.fixed': 'integration/stage0-12:3e173b1cd52120f4cedd26e0f43348864119ec47'
    } },
    sheets: [{ id: 'sheet-1', name: 'Лист 1', widthUm: 420000, heightUm: 297000,
      symbols: [
        { id: 'r1', kind: 'resistor.fixed', ref: 'R1', value: '10к', x: 85000, y: 90000, rotation: 0 },
        { id: 'c1', kind: 'capacitor.fixed', ref: 'C1', value: '100н', x: 230000, y: 130000, rotation: 0 },
        { id: 'da1', kind: 'ic.tl494.demo', ref: 'DA1', value: 'TL494 · ДЕМО', x: 165000, y: 185000, rotation: 0 }
      ], nets: [], wires: [], junctions: [], graphics: [] }] };
}
export function sheet(project, id) { return project.sheets.find(s=>s.id===id) ?? project.sheets[0]; }
export function transformedPin(symbol, number) {
  const def=LIBRARY[symbol.kind]; if(!def) throw Error('UNKNOWN_SYMBOL');
  const pin=def.pins.find(p=>p.number===String(number)); if(!pin) throw Error('INVALID_PINREF');
  const n=((symbol.rotation % 360)+360)%360;
  if(![0,90,180,270].includes(n)) throw Error('INVALID_ROTATION');
  const x=n===0?pin.x:n===90?-pin.y:n===180?-pin.x:pin.y;
  const y=n===0?pin.y:n===90?pin.x:n===180?-pin.y:-pin.x;
  return { x: symbol.x+x, y: symbol.y+y };
}
export function resolvePin(s,pin) {const sym=s.symbols.find(e=>e.id===pin.symbolId); if(!sym) throw Error('INVALID_PINREF');return transformedPin(sym,pin.number);}
export function pinKey(p) {return `${p.symbolId}:${p.number}`;}
export function declaredNet(s,p) {return s.nets.find(n=>n.members.some(m=>pinKey(m)===pinKey(p))) ?? null;}
export function nextReference(s,kind){const prefix=LIBRARY[kind].refPrefix;let n=1;while(s.symbols.some(e=>e.ref===`${prefix}${n}`))n++;return `${prefix}${n}`;}
export function snap(v,stepUm,enabled) {return enabled?Math.round(v/stepUm)*stepUm:Math.round(v);}
export function routePoints(a,b) {
  if(a.x===b.x||a.y===b.y) return [a,b];
  const mid=Math.round((a.x+b.x)/2);
  return [a,{x:mid,y:a.y},{x:mid,y:b.y},b];
}
export function pointOnSegment(p,a,b){return (a.x===b.x&&p.x===a.x&&p.y>=Math.min(a.y,b.y)&&p.y<=Math.max(a.y,b.y))||(a.y===b.y&&p.y===a.y&&p.x>=Math.min(a.x,b.x)&&p.x<=Math.max(a.x,b.x));}
// Build the complete operation first. Rejecting an invalid route must never leave
// an extra Net.member or half-authored Wire in the current document.
export function appendWire(s,start,end,waypoints=[]) {
  if(!start||!end||pinKey(start)===pinKey(end)) throw Error('INVALID_WIRE_ENDPOINTS');
  if(!Array.isArray(waypoints)||waypoints.length>128||waypoints.some(p=>
    !p||!Number.isSafeInteger(p.x)||!Number.isSafeInteger(p.y)||
    Math.abs(p.x)>1_000_000_000||Math.abs(p.y)>1_000_000_000
  ))throw Error('INVALID_WAYPOINTS');
  const a=resolvePin(s,start),b=resolvePin(s,end);
  const netA=declaredNet(s,start),netB=declaredNet(s,end);
  if(netA?.id!==netB?.id&&(netA||netB)) {
    const existing=netA||netB;
    if(existing.source!=='user'||(netA&&netB))throw Error('NET_MERGE_DENIED');
  }
  const existing=netA||netB||null;
  const net=existing?deep(existing):{
    id:uid('net'),name:`N$${s.nets.length+1}`,members:[deep(start),deep(end)],source:'user'
  };
  if(existing&&(!netA||!netB))net.members.push(deep(netA?end:start));
  const links=[a,...waypoints,b];let points=[];
  for(let i=0;i<links.length-1;i++){
    let part=routePoints(links[i],links[i+1]);
    if(points.length&&part.length&&points.at(-1).x===part[0].x&&points.at(-1).y===part[0].y)part=part.slice(1);
    points.push(...part);
  }
  points=points.filter((p,i)=>i===0||p.x!==points[i-1].x||p.y!==points[i-1].y);
  if(points.length<2)throw Error('ZERO_LENGTH_WIRE');
  const wire={id:uid('wire'),netId:net.id,start:{type:'pin',pin:deep(start)},end:{type:'pin',pin:deep(end)},points};
  const nets=existing?s.nets.map(n=>n.id===existing.id?net:n):[...s.nets,net];
  const wires=[...s.wires,wire];
  verifyProject({format:FORMAT,version:VERSION,sheets:[{...s,nets,wires}]});
  s.nets=nets;s.wires=wires;
  return wire;
}
// Remove dependent junctions instead of leaving a dangling connectedWireIds entry.
// This prototype represents no branch-splice graph; the production #123 engine
// must replace this with a typed transaction / explicit junction split.
export function removeWire(s,wireId){
  if(!s.wires.some(w=>w.id===wireId))throw Error('UNKNOWN_WIRE');
  const wires=s.wires.filter(w=>w.id!==wireId);
  const junctions=s.junctions.map(j=>({...j,connectedWireIds:j.connectedWireIds.filter(id=>id!==wireId)}))
    .filter(j=>j.connectedWireIds.length>=2);
  verifyProject({format:FORMAT,version:VERSION,sheets:[{...s,wires,junctions}]});
  s.wires=wires;s.junctions=junctions;
}
export function moveSegment(wire,index,deltaUm){
  if(index<=0 || index>=wire.points.length-2)throw Error('ENDPOINT_SEGMENT_LOCKED');
  const a=wire.points[index],b=wire.points[index+1];
  if(a.x===b.x){a.x+=deltaUm;b.x+=deltaUm;} else if(a.y===b.y){a.y+=deltaUm;b.y+=deltaUm;} else throw Error('NON_ORTHOGONAL_SEGMENT');
}
export function reanchor(s,symbolId){
  for(const w of s.wires){
    for(const side of ['start','end']){
      const end=w[side];if(end?.type!=='pin'||end.pin.symbolId!==symbolId)continue;
      const p=resolvePin(s,end.pin),at=side==='start'?0:w.points.length-1,old=w.points[at];
      if(w.points.length<3){ w.points=routePoints(resolvePin(s,w.start.pin),resolvePin(s,w.end.pin)); continue; }
      const near=side==='start'?1:w.points.length-2;
      const adjacent=w.points[near];
      if(adjacent.y===old.y)adjacent.y=p.y;else if(adjacent.x===old.x)adjacent.x=p.x;
      w.points[at]=p;
    }
  }
}
const safeUm=v=>Number.isSafeInteger(v)&&Math.abs(v)<=1_000_000_000;
export function verifyProject(project){
  const errs=[];
  if(project?.format!==FORMAT||project.version!==VERSION||!Array.isArray(project.sheets))throw Error('UNSUPPORTED_PROJECT_FORMAT');
  if(!project.sheets.length||project.sheets.length>128)throw Error('INVALID_SHEET_COUNT');
  const sheetIds=new Set();
  for(const s of project.sheets){
    if(!s||typeof s.id!=='string'||!s.id||sheetIds.has(s.id)||
      !safeUm(s.widthUm)||!safeUm(s.heightUm)||s.widthUm<=0||s.heightUm<=0||
      !Array.isArray(s.symbols)||!Array.isArray(s.wires)||!Array.isArray(s.nets)||
      !Array.isArray(s.junctions)||!Array.isArray(s.graphics))throw Error('INVALID_SHEET');
    sheetIds.add(s.id);
    const idSet=new Set(),refs=new Set();
    for(const sym of s.symbols){
      if(!sym||!LIBRARY[sym.kind]||!safeUm(sym.x)||!safeUm(sym.y)||
        ![0,90,180,270].includes(sym.rotation)||typeof sym.id!=='string'||!sym.id||
        typeof sym.ref!=='string'||!sym.ref||idSet.has(sym.id)||refs.has(sym.ref))errs.push('INVALID_SYMBOL');
      idSet.add(sym?.id);refs.add(sym?.ref);
    }
    const netIds=new Set(),memberOwners=new Map();
    for(const net of s.nets){
      if(!net||typeof net.id!=='string'||!net.id||netIds.has(net.id)||
        typeof net.name!=='string'||!net.name||!Array.isArray(net.members)||!net.members.length){errs.push('INVALID_NET');continue;}
      netIds.add(net.id);
      for(const p of net.members){
        try{
          resolvePin(s,p);
          const key=pinKey(p);
          if(memberOwners.has(key))errs.push(`DUPLICATE_NET_MEMBERSHIP:${key}`);
          memberOwners.set(key,net.id);
        }catch{errs.push(`INVALID_NET_PIN:${net.name}`);}
      }
    }
    const wireIds=new Set();
    for(const w of s.wires){
      try {
        if(!w||typeof w.id!=='string'||!w.id||wireIds.has(w.id)||
          !netIds.has(w.netId)||!Array.isArray(w.points)||w.points.length<2)throw Error('NET_OR_POINTS');
        wireIds.add(w.id);
        const declared=s.nets.find(n=>n.id===w.netId);
        for(const side of ['start','end']){
          if(w[side]?.type!=='pin'||!w[side].pin)throw Error('INVALID_WIRE_ANCHOR');
          const pin=w[side].pin;
          if(!declared.members.some(p=>pinKey(p)===pinKey(pin)))throw Error('PIN_NET_MISMATCH');
          const pos=resolvePin(s,pin),e=w.points[side==='start'?0:w.points.length-1];
          if(pos.x!==e.x||pos.y!==e.y)throw Error('PIN_DRIFT');
        }
        for(let i=0;i<w.points.length;i++){
          const p=w.points[i];if(!p||!safeUm(p.x)||!safeUm(p.y))throw Error('INVALID_COORDINATE');
          if(i>0){const prior=w.points[i-1];if(p.x===prior.x&&p.y===prior.y)throw Error('ZERO_LENGTH_SEGMENT');
            if(p.x!==prior.x&&p.y!==prior.y)throw Error('NON_ORTHOGONAL');}
        }
      }catch(e){errs.push(`${w?.id||'wire'}:${e.message}`);}
    }
    for(const j of s.junctions){
      if(!j||!safeUm(j.x)||!safeUm(j.y)||!Array.isArray(j.connectedWireIds)||
        j.connectedWireIds.length<2||new Set(j.connectedWireIds).size!==j.connectedWireIds.length){errs.push('INVALID_JUNCTION_MEMBERS');continue;}
      if(!netIds.has(j.netId)||!j.connectedWireIds.every(id=>{
        const wire=s.wires.find(w=>w.id===id);return wire?.netId===j.netId&&wire.points.some((p,i)=>i>0&&pointOnSegment(j,wire.points[i-1],p));
      }))errs.push('INVALID_JUNCTION');
    }
  }
  if(errs.length)throw Error(errs.join('; '));return true;
}
export function serialized(p) {verifyProject(p);return JSON.stringify(p,null,2)+'\n';}
const xml=t=>String(t).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
const mm=n=>(n/UM).toFixed(3).replace(/\.?0+$/,'')||'0';
const pos=p=>`${mm(p.x)},${mm(p.y)}`;
export function symbolArtwork(sym){
  const {kind,ref,value}=sym;
  let shapes='';
  if(kind==='resistor.fixed')shapes='<path d="M -8 0 H -5 M 5 0 H 8"/><rect x="-5" y="-2" width="10" height="4"/>';
  else if(kind==='capacitor.fixed')shapes='<path d="M -8 0 H -0.75 M 0.75 0 H 8 M -0.75 -4 V 4 M 0.75 -4 V 4"/>';
  else if(kind==='ic.tl494.demo'){
    shapes='<rect x="-16" y="-21" width="32" height="42"/>';
    for(const p of LIBRARY[kind].pins){
      const y=mm(p.y),x0=p.x<0?-22:16,x1=p.x<0?-16:22;
      shapes+=`<line x1="${x0}" y1="${y}" x2="${x1}" y2="${y}"/>`;
      shapes+=`<text x="${p.x<0?-14.5:14.5}" y="${Number(y)+0.9}" text-anchor="${p.x<0?'start':'end'}" font-size="2.5" fill="currentColor" stroke="none">${xml(p.number)}</text>`;
    }
    shapes+='<text x="0" y="-2" font-size="4" text-anchor="middle" stroke="none" fill="currentColor">TL494</text><text x="0" y="3" font-size="2.5" text-anchor="middle" stroke="none" fill="currentColor">DEMO / DRAFT</text>';
  }
  return `<g class="symbol-art" data-instance-id="${xml(sym.id)}" transform="translate(${mm(sym.x)} ${mm(sym.y)}) rotate(${sym.rotation})" stroke="currentColor" stroke-width="0.3" stroke-linejoin="miter" stroke-linecap="butt" fill="none">${shapes}<text x="0" y="${kind==='ic.tl494.demo'?-23:-7}" text-anchor="middle" fill="currentColor" stroke="none" font-family="Arial, sans-serif" font-size="3.4">${xml(ref)}${kind==='ic.tl494.demo'?'':` · ${xml(value)}`}</text></g>`;
}
export function exportSvg(project, sheetId){
  verifyProject(project);const s=sheet(project,sheetId),w=mm(s.widthUm),h=mm(s.heightUm);
  const symbols=s.symbols.map(symbolArtwork).join('');
  const wires=s.wires.map(w=>`<polyline data-wire-id="${xml(w.id)}" data-net-id="${xml(w.netId)}" points="${w.points.map(pos).join(' ')}"/>`).join('');
  const junctions=s.junctions.map(j=>`<circle data-junction-net="${xml(j.netId)}" cx="${mm(j.x)}" cy="${mm(j.y)}" r="0.65" fill="black"/>`).join('');
  const graphics=s.graphics.map(g=>g.type==='line'?`<line data-non-electrical="true" x1="${mm(g.a.x)}" y1="${mm(g.a.y)}" x2="${mm(g.b.x)}" y2="${mm(g.b.y)}"/>`:'').join('');
  return `<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="${w}mm" height="${h}mm" viewBox="0 0 ${w} ${h}"><title>${xml(project.title)} — ${xml(s.name)} (CAD R0, not approved)</title><rect width="${w}" height="${h}" fill="white"/><g color="#111" stroke="black" stroke-width="0.3" fill="none">${symbols}</g><g stroke="black" fill="none" stroke-width="0.3" stroke-linecap="butt" stroke-linejoin="miter">${wires}${graphics}</g>${junctions}</svg>\n`;
}
// Insert standards-defined PNG pHYs chunk (11811 px/m = ~300 dpi) without modifying image pixels.
function crc32(bytes){let crc=-1;for(const b of bytes){crc^=b;for(let j=0;j<8;j++)crc=(crc>>>1)^((crc&1)?0xedb88320:0);}return(crc^(-1))>>>0;}
export function withPngDpi(input,dpi=300){
  if(!Number.isInteger(dpi)||dpi<1||dpi>2400) throw Error('INVALID_DPI');
  const src=new Uint8Array(input),signature=[137,80,78,71,13,10,26,10];
  if(src.length<33||!signature.every((v,i)=>src[i]===v))throw Error('NOT_PNG');
  const ppm=Math.round(dpi/0.0254),chunk=new Uint8Array(21),cv=new DataView(chunk.buffer);
  cv.setUint32(0,9);chunk.set([112,72,89,115],4);cv.setUint32(8,ppm);cv.setUint32(12,ppm);chunk[16]=1;
  cv.setUint32(17,crc32(chunk.slice(4,17)));
  const dataView=new DataView(src.buffer,src.byteOffset,src.byteLength),parts=[src.slice(0,8)];
  let offset=8,seenHeader=false,seenEnd=false;
  while(offset<src.length){
    if(offset+12>src.length)throw Error('CORRUPT_PNG');
    const len=dataView.getUint32(offset),end=offset+len+12;
    if(end>src.length)throw Error('CORRUPT_PNG');
    const tag=String.fromCharCode(...src.slice(offset+4,offset+8));
    if(!seenHeader&&tag!=='IHDR')throw Error('CORRUPT_PNG');
    if(tag!=='pHYs')parts.push(src.slice(offset,end));
    if(tag==='IHDR'){seenHeader=true;parts.push(chunk);}
    if(tag==='IEND'){seenEnd=true;break;}
    offset=end;
  }
  if(!seenEnd)throw Error('CORRUPT_PNG');
  const size=parts.reduce((n,p)=>n+p.length,0),out=new Uint8Array(size);let at=0;
  for(const p of parts){out.set(p,at);at+=p.length;}return out;
}
