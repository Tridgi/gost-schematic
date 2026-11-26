/** Physical SVG/PNG browser preview of a previously validated ProjectFileV2.
 * The frozen PinRef/Net inventory is preserved in metadata. SVG ink intersection
 * never implies connectivity. This is NOT a normative GOST font/print approval.
 * Production-certified export remains the canonical Python exporter (#130).
 */
import type { ProjectFileV2, PointUm, SymbolInstance, Primitive } from '../model/contract';
import {noteLayout} from '../model/symbol-notes.mjs';
import {curveGeometry} from '../model/curves.mjs';
import { worldPin } from '../model/contract.ts';
import { projectToCanvasScene } from '../canvas/scene-projection.mjs';
import {planComponentLabels} from '../canvas/component-labels.ts';

const esc=(x:unknown):string=>String(x).replace(/[&<>"']/g,c=>({
  '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'
}[c]!));
function safe(n:number):number{
  if(!Number.isSafeInteger(n)||Math.abs(n)>1_000_000_000)throw Error('INVALID_UM');
  return n;
}
const mm=(n:number):string=>(safe(n)/1000).toFixed(3).replace(/\.000$/,'');
const pos=(p:PointUm):string=>mm(p[0])+','+mm(p[1]);
function stroke(a:PointUm,b:PointUm,width:number,attrs=''):string{
  if(a[0]===b[0]&&a[1]===b[1])throw Error('ZERO_LENGTH_GRAPHIC');
  if(safe(width)<=0)throw Error('INVALID_STROKE_UM');
  return '<line x1="'+mm(a[0])+'" y1="'+mm(a[1])+'" x2="'+mm(b[0])+
    '" y2="'+mm(b[1])+'" stroke="#000" stroke-width="'+mm(width)+
    '" stroke-linecap="butt" fill="none" '+attrs+'/>';
}
function primitiveInk(inst:SymbolInstance,primitive:Primitive):string{
  const points=primitive.points_um.map(p=>worldPin(inst,p));
  if(primitive.kind==='circle'||primitive.kind==='semicircle'){
    const curve=curveGeometry(primitive.kind,points),r=mm(curve.radius);
    const style=' stroke="#000" stroke-width="'+mm(primitive.stroke_um)+'" fill="none"/>';
    if(primitive.kind==='circle')return '<circle cx="'+mm(curve.center[0])+'" cy="'+mm(curve.center[1])+'" r="'+r+'"'+style;
    return '<path d="M '+pos(points[0])+' A '+r+' '+r+' 0 0 '+curve.sweep+' '+pos(points[2])+'"'+style;
  }
  if(primitive.kind==='rect'){
    if(points.length!==2)throw Error('INVALID_RECT');
    const [a,b]=points;const left=Math.min(a[0],b[0]),top=Math.min(a[1],b[1]);
    const w=Math.abs(a[0]-b[0]),h=Math.abs(a[1]-b[1]);
    if(w===0||h===0)throw Error('DEGENERATE_RECT');
    return '<rect x="'+mm(left)+'" y="'+mm(top)+'" width="'+mm(w)+
      '" height="'+mm(h)+'" stroke="#000" stroke-width="'+mm(primitive.stroke_um)+
      '" fill="none"/>';
  }
  if(primitive.kind==='line'&&points.length!==2)throw Error('INVALID_LINE');
  if(primitive.kind==='polyline'&&points.length<2)throw Error('INVALID_POLYLINE');
  if(!['line','polyline'].includes(primitive.kind))throw Error('UNKNOWN_PRIMITIVE');
  return points.slice(1).map((p,i)=>stroke(points[i],p,primitive.stroke_um)).join('');
}
/** Source-locked preview: coordinates and stroke thicknesses are physical millimetres. */
export function renderProjectPreviewSVG(file:ProjectFileV2,sheetId:string):string{
  if(file?.format!=='gscad-project'||file.format_version!==2)throw Error('INVALID_PROJECT_V2');
  // Reject malformed external ids, parts, foreign graphic pin references, duplicate entities.
  const scene=projectToCanvasScene(file,sheetId);
  const labelPlan=planComponentLabels(file,sheetId,scene);
  const p=file.project,sh=p.sheets.find(s=>s.id===sheetId);
  if(!sh)throw Error('UNKNOWN_SHEET');
  const width=mm(sh.frame.size_um[0]),height=mm(sh.frame.size_um[1]);
  const printable=new Set(sh.layers.filter(l=>l.visible&&l.printable&&l.kind!=='diagnostics').map(l=>l.id));
  const byComp=new Map(p.components.map(c=>[c.id,c]));
  const bySymbol=new Map(p.symbol_definitions.map(s=>[s.id,s]));
  const byNet=new Map(p.nets.map(n=>[n.id,n]));
  const nets=p.nets.map(n=>({
    id:n.id,name:n.name,route_status:n.route_status,
    members:n.members.map(m=>[m.component_id,m.physical_pin_number])
  }));
  const out=[
    '<svg xmlns="http://www.w3.org/2000/svg" width="'+width+'mm" height="'+height+
    'mm" viewBox="0 0 '+width+' '+height+'" data-source-model="gscad-project-v2"'+
    ' data-font-status="unverified-preview" data-component-label-count="'+labelPlan.labels.length+'" data-unplaced-label-count="'+labelPlan.unplaced.length+'" data-source-net-count="'+p.nets.length+
    '" data-authored-wire-count="'+sh.wires.length+'">',
    '<metadata data-kind="source-netlist" data-electrical="declared-not-geometry-inferred">'+
    esc(JSON.stringify(nets))+'</metadata>',
    '<metadata data-kind="source-provenance">'+esc(JSON.stringify(p.provenance))+'</metadata>',
    '<rect x="0" y="0" width="'+width+'" height="'+height+'" fill="white"/>'
  ];
  for(const inst of sh.instances){
    if(!printable.has(inst.layer_id))continue;
    const c=byComp.get(inst.component_id),s=bySymbol.get(inst.symbol_id);
    if(!c||!s)throw Error('UNKNOWN_INSTANCE_PART');
    out.push('<g data-layer="symbols" data-instance-id="'+esc(inst.id)+'"'+
      ' data-component-id="'+esc(c.id)+'" data-reference="'+esc(c.refdes)+'"'+
      ' data-pinrefs="'+esc(JSON.stringify(s.pins.map(pin=>[c.id,pin.physical_pin_number])))+'">');
    for(const prim of s.graphics)out.push(primitiveInk(inst,prim));
    for(const n of s.constant_annotations??[]){
      const layout=noteLayout(n,worldPin(inst,n.at_um));
      out.push('<text data-symbol-note="'+esc(n.key)+'" data-electrical="false" x="'+mm(layout.baseline[0])+'" y="'+mm(layout.baseline[1])+'" text-anchor="'+layout.anchor+'" font-size="'+mm(n.height_um)+'" font-family="OpenGost Type A, sans-serif" fill="#000" stroke="none">'+esc(n.text)+'</text>');
    }
    out.push('</g>');
  }
  for(const wire of sh.wires){
    if(!printable.has(wire.layer_id))continue;
    if(!byNet.has(wire.net_id))throw Error('UNKNOWN_WIRE_NET');
    const vertices=new Map(wire.vertices.map(v=>[v.id,v.at_um]));
    out.push('<g data-layer="wires" data-wire-id="'+esc(wire.id)+
      '" data-net-id="'+esc(wire.net_id)+'">');
    for(const seg of wire.segments){
      const a=vertices.get(seg.from_vertex_id),b=vertices.get(seg.to_vertex_id);
      if(!a||!b)throw Error('MISSING_VERTEX');
      if(a[0]!==b[0]&&a[1]!==b[1])throw Error('NONORTHOGONAL_WIRE');
      out.push(stroke(a,b,300,'data-segment-id="'+esc(seg.id)+'"'));
    }
    out.push('</g>');
  }
  // Only signed junction records create dots. Splices are deliberately invisible.
  for(const junction of sh.junctions)if(printable.has(junction.layer_id)){
    out.push('<circle data-layer="explicit-junctions" data-net-id="'+esc(junction.net_id)+
      '" data-junction-id="'+esc(junction.id)+'" cx="'+mm(junction.at_um[0])+
      '" cy="'+mm(junction.at_um[1])+'" r="0.55" fill="#000"/>');
  }
  for(const graphic of sh.graphics)if(printable.has(graphic.layer_id)){
    out.push('<g data-layer="graphics" data-electrical="false" data-kind="'+esc(graphic.kind)+
      '" data-id="'+esc(graphic.id)+'">');
    const pts=graphic.points_um;
    if(pts.length<2)throw Error('INVALID_GRAPHIC');
    for(let i=1;i<pts.length;i++)out.push(stroke(pts[i-1],pts[i],graphic.stroke_um));
    out.push('</g>');
  }
  for(const item of [...sh.texts,...sh.labels])if(printable.has(item.layer_id)&&item.text){
    out.push('<text data-layer="annotations" x="'+mm(item.at_um[0])+
      '" y="'+mm(item.at_um[1])+'" font-size="'+mm('height_um' in item?item.height_um:3500)+
      '" font-family="OpenGost Type A, sans-serif" fill="#000"'+('rotation_deg' in item&&item.rotation_deg?' transform="rotate('+item.rotation_deg+' '+mm(item.at_um[0])+' '+mm(item.at_um[1])+')"':'')+'>'+esc(item.text)+'</text>');
  }
  out.push('<metadata data-kind="unplaced-component-labels">'+esc(JSON.stringify(labelPlan.unplaced))+'</metadata>');
  for(const l of labelPlan.labels){
    out.push('<g data-layer="component-labels" data-electrical="false" data-instance-id="'+esc(l.instanceId)+'">');
    const line=(value:string,y:number,role:string)=>'<text data-label-role="'+role+'" x="'+mm(l.x)+'" y="'+mm(y)+'" text-anchor="middle" font-family="OpenGost Type A, monospace" font-size="'+mm(l.heightUm)+'" fill="#000" stroke="none">'+esc(value)+'</text>';
    out.push(line(l.refdes,l.y,'reference'));
    if(l.value)out.push(line(l.value,l.y+l.lineStepUm,'value'));
    out.push('</g>');
  }
  out.push('</svg>');
  return out.join('');
}
function writeU32(dst:Uint8Array,offset:number,v:number){
  dst[offset]=(v>>>24)&255;dst[offset+1]=(v>>>16)&255;
  dst[offset+2]=(v>>>8)&255;dst[offset+3]=v&255;
}
function readU32(src:Uint8Array,i:number):number{
  return ((src[i]*0x1000000)+(src[i+1]<<16)+(src[i+2]<<8)+src[i+3])>>>0;
}
function crc32(src:Uint8Array):number{
  let crc=0xffffffff;
  for(const b of src){
    crc^=b;
    for(let k=0;k<8;k++)crc=(crc>>>1)^(crc&1?0xedb88320:0);
  }
  return (crc^0xffffffff)>>>0;
}
/** Add/replace pHYs at 300 DPI (11811 pixels per metre); do not merely relabel pixels. */
export function setPng300Dpi(src:Uint8Array):Uint8Array{
  const sig=[137,80,78,71,13,10,26,10];
  if(sig.some((v,i)=>src[i]!==v))throw Error('NOT_PNG');
  const phys=new Uint8Array(21);writeU32(phys,0,9);
  phys.set([112,72,89,115],4);writeU32(phys,8,11811);writeU32(phys,12,11811);
  phys[16]=1;writeU32(phys,17,crc32(phys.slice(4,17)));
  const chunks:Uint8Array[]=[src.slice(0,8)];
  let offset=8,hasIHDR=false,hasIDAT=false,hasIEND=false;
  while(offset<src.length){
    if(offset+12>src.length)throw Error('TRUNCATED_PNG');
    const length=readU32(src,offset),end=offset+12+length;
    if(end>src.length||length>src.length)throw Error('TRUNCATED_PNG');
    const name=String.fromCharCode(...src.slice(offset+4,offset+8));
    // Reject damaged chunks before tagging any raster as a physical 300-DPI PNG.
    if(crc32(src.slice(offset+4,end-4))!==readU32(src,end-4))
      throw Error('INVALID_PNG_CRC');
    if(!hasIHDR && (name!=='IHDR'||offset!==8))throw Error('INVALID_PNG_STRUCTURE');
    if(name==='IHDR'){
      if(hasIHDR||length!==13||readU32(src,offset+8)===0||readU32(src,offset+12)===0)
        throw Error('INVALID_PNG_STRUCTURE');
      hasIHDR=true;chunks.push(src.slice(offset,end),phys);
    }else if(name==='IDAT'){
      hasIDAT=true;chunks.push(src.slice(offset,end));
    }else if(name==='IEND'){
      if(length!==0||!hasIDAT||end!==src.length)throw Error('INVALID_PNG_STRUCTURE');
      hasIEND=true;chunks.push(src.slice(offset,end));
      break;
    }else if(name!=='pHYs')chunks.push(src.slice(offset,end));
    offset=end;
  }
  if(!hasIHDR||!hasIDAT||!hasIEND)throw Error('INVALID_PNG_STRUCTURE');
  const n=chunks.reduce((a,c)=>a+c.length,0),out=new Uint8Array(n);
  let cursor=0;for(const chunk of chunks){out.set(chunk,cursor);cursor+=chunk.length;}
  return out;
}
export async function renderPreviewPng300(svg:string,sizeUm:PointUm):Promise<Blob>{
  const width=Math.round(safe(sizeUm[0])/25400*300),height=Math.round(safe(sizeUm[1])/25400*300);
  if(width<=0||height<=0||width*height>40_000_000)throw Error('RASTER_SIZE_UNSUPPORTED');
  const source=URL.createObjectURL(new Blob([svg],{type:'image/svg+xml;charset=utf-8'}));
  try{
    const image=new Image();
    await new Promise<void>((resolve,reject)=>{
      image.onload=()=>resolve();image.onerror=()=>reject(Error('SVG_IMAGE_FAILED'));
      image.src=source;
    });
    const canvas=document.createElement('canvas');
    canvas.width=width;canvas.height=height;
    const ctx=canvas.getContext('2d');
    if(!ctx)throw Error('PNG_CONTEXT_UNAVAILABLE');
    ctx.fillStyle='white';ctx.fillRect(0,0,width,height);
    ctx.drawImage(image,0,0,width,height);
    const raw=await new Promise<Blob>((resolve,reject)=>
      canvas.toBlob(b=>b?resolve(b):reject(Error('PNG_ENCODING_FAILED')),'image/png'));
    return new Blob([setPng300Dpi(new Uint8Array(await raw.arrayBuffer()))],{type:'image/png'});
  }finally{URL.revokeObjectURL(source);}
}
