/** CHAT 4 / #120: read-only projection of #122 canonical ProjectFileV2 to canvas scene.
 * Does not modify source Nets, wire connectivity, or render graphics as electrical anchors.
 */
function projectToCanvasScene(file,sheetId){
 const deny=(code)=>{throw Error(code)};
 const validPoint=p=>Array.isArray(p)&&p.length===2&&p.every(n=>Number.isSafeInteger(n)&&Math.abs(n)<=1e9);
 const point=p=>{if(!validPoint(p))deny("INVALID_UM_POINT");return [p[0],p[1]]};
 if(file?.format!=="gscad-project"||file.format_version!==2||!file.project)deny("UNSUPPORTED_PROJECT_V2");
 const p=file.project;
 if(![p.components,p.part_definitions,p.symbol_definitions,p.sheets,p.nets].every(Array.isArray))deny("INVALID_PROJECT_COLLECTIONS");
 const sheet=p.sheets.find(s=>s.id===sheetId);
 if(!sheet)deny("UNKNOWN_SHEET");
 const unique=(items,code)=>{const m=new Map();for(const item of items){if(!item?.id||m.has(item.id))deny(code);m.set(item.id,item)}return m};
 const components=unique(p.components,"DUPLICATE_COMPONENT");
 const parts=unique(p.part_definitions,"DUPLICATE_PART");
 const symbols=unique(p.symbol_definitions,"DUPLICATE_SYMBOL");
 if(!Array.isArray(sheet.instances)||!Array.isArray(sheet.wires)||!Array.isArray(sheet.junctions)||!Array.isArray(sheet.splices)||!Array.isArray(sheet.graphics))deny("INVALID_SHEET_COLLECTIONS");
 const line=(a,b)=>({from_um:point(a),to_um:point(b)});
 const graphicsToStrokes=g=>{
  if(!Array.isArray(g.points_um))deny("INVALID_GRAPHIC_POINTS");
  const pts=g.points_um.map(point);
  if(g.kind==="line"){if(pts.length!==2)deny("INVALID_LINE");return [line(pts[0],pts[1])]}
  if(g.kind==="polyline"){if(pts.length<2)deny("INVALID_POLYLINE");return pts.slice(1).map((t,i)=>line(pts[i],t))}
  if(g.kind==="rect"){
   if(pts.length!==2)deny("INVALID_RECT");
   const [a,b]=pts;if(a[0]===b[0]||a[1]===b[1])deny("ZERO_AREA_RECT");
   const tl=[Math.min(a[0],b[0]),Math.min(a[1],b[1])],br=[Math.max(a[0],b[0]),Math.max(a[1],b[1])];
   return [line(tl,[br[0],tl[1]]),line([br[0],tl[1]],br),line(br,[tl[0],br[1]]),line([tl[0],br[1]],tl)];
  }
  deny("UNKNOWN_GRAPHIC_KIND");
 };
 const instances=unique(sheet.instances,"DUPLICATE_INSTANCE"),sourceSymbols=[];
 for(const i of instances.values()){
  const c=components.get(i.component_id),s=symbols.get(i.symbol_id);
  if(!c||!s)deny("MISSING_INSTANCE_DEFINITION");
  const part=parts.get(c.part_id);
  if(!part||s.part_id!==part.id||!Array.isArray(part.symbol_ids)||!part.symbol_ids.includes(s.id))deny("PART_SYMBOL_MISMATCH");
  if(![0,90,180,270].includes(i.rotation_deg)||typeof i.mirror_x!=="boolean")deny("INVALID_SYMBOL_TRANSFORM");
  const physical=new Set((part.physical_pins||[]).map(pin=>pin.number)),seen=new Set();
  const sides={left:"left",right:"right",top:"up",bottom:"down"};
  const pins=(s.pins||[]).map(pin=>{
   if(!physical.has(pin.physical_pin_number)||seen.has(pin.physical_pin_number))deny("INVALID_SYMBOL_PIN");
   seen.add(pin.physical_pin_number);
   const normal=sides[pin.side];if(!normal)deny("UNKNOWN_PIN_SIDE");
   return {physical_pin_number:pin.physical_pin_number,at_um:point(pin.at_um),normal};
  });
  const strokes=(s.graphics||[]).filter(g=>g.kind!=='circle').flatMap(graphicsToStrokes);
  const circles=(s.graphics||[]).filter(g=>g.kind==='circle').map(g=>{
   if(!Array.isArray(g.points_um)||g.points_um.length!==2)deny('INVALID_CIRCLE');
   const [a,b]=g.points_um.map(point),r=b[0]-a[0];
   if(b[1]!==a[1]||r<=0||Math.max(Math.abs(a[0]),Math.abs(a[1]))+r>1e9||
      !Number.isSafeInteger(g.stroke_um)||g.stroke_um<=0||g.stroke_um>100000)deny('INVALID_CIRCLE');
   return {center_um:a,radius_um:r,stroke_um:g.stroke_um};
  });
  sourceSymbols.push({instance_id:i.id,component_id:c.id,origin_um:point(i.origin_um),rotation_deg:i.rotation_deg,mirror_x:i.mirror_x,pins,strokes,circles,status:s.status,layer_id:i.layer_id});
 }
 const visualGraphics=sheet.graphics.map(g=>{
  const isB=g.kind==="source_b_continuation";
  // Frozen E695 continuation b is pure source ink; it cannot bind electrical Nets,
  // terminals, junctions or the wire domain. Reject malformed legacy attachments.
  if(isB&&(["net_id","pinrefs","wire_id","electrical","anchor","members","junction_id","splice_id"].some(k=>Object.prototype.hasOwnProperty.call(g,k))))deny("NON_ELECTRICAL_GRAPHIC");
  if(isB&&(!Array.isArray(g.points_um)||g.points_um.length!==2))deny("INVALID_B_GRAPHIC");
  if(!isB&&!["line","polyline"].includes(g.kind))deny("UNKNOWN_SHEET_GRAPHIC");
  return {id:g.id,layer_id:g.layer_id,kind:g.kind,
   source_role:isB?"source_b_continuation":g.source_role??"none",
   electrical:false,strokes:graphicsToStrokes(isB?{...g,kind:"line"}:g)};
 });
 const clone=v=>JSON.parse(JSON.stringify(v));
 return {symbols:sourceSymbols,wires:clone(sheet.wires),junctions:clone(sheet.junctions),splices:clone(sheet.splices),graphics:visualGraphics};
}
export {projectToCanvasScene};
