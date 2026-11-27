/** Read-only declared topology inventory. No function, polarity, or power
 * classification from coordinates or names. Source labels remain verbatim. */
export function topologyInventory(file,sheetId){
 const p=file.project,sh=p.sheets.find(s=>s.id===sheetId);
 if(!sh)throw Error('UNKNOWN_SHEET');
 const parts=new Map(p.part_definitions.map(d=>[d.id,d]));
 const defs=new Map(p.symbol_definitions.map(d=>[d.id,d]));
 const comps=new Map(p.components.map(c=>[c.id,c]));
 const local=new Map(sh.instances.map(i=>[i.component_id,i]));
 const key=p=>JSON.stringify([p.component_id,p.physical_pin_number]);
 const netByPin=new Map();
 const nets=p.nets.filter(n=>n.members.some(m=>local.has(m.component_id))).map(n=>{
  const devices=new Set(n.members.map(m=>m.component_id));
  const localDevices=[...devices].filter(id=>local.has(id));
  const evidence=n.members.flatMap(m=>{
   const c=comps.get(m.component_id),pin=parts.get(c?.part_id)?.physical_pins.find(v=>v.number===m.physical_pin_number);
   return pin&&(pin.electrical_type==='power_input'||pin.electrical_type==='power_output')?
    [{refdes:c.refdes,pin:m.physical_pin_number,type:pin.electrical_type}]:[];
  });
  const item={id:n.id,name:n.name,pins:n.members.length,devices:devices.size,localDevices:localDevices.length,
   externalDevices:devices.size-localDevices.length,powerEvidence:evidence};
  for(const m of n.members)netByPin.set(key(m),{net:n,item});
  return item;
 });
 const hubs=sh.instances.flatMap(i=>{
  const d=defs.get(i.symbol_id),c=comps.get(i.component_id);
  if(!d||!c||d.pins.length<4)return [];
  const part=parts.get(c.part_id),neighbors=new Set(),netIds=new Set();
  const pins=d.pins.map(pin=>{
   const number=pin.physical_pin_number,info=netByPin.get(key({component_id:c.id,physical_pin_number:number}));
   const related=info?[...new Set(info.net.members.filter(m=>m.component_id!==c.id).map(m=>m.component_id))]:[];
   for(const id of related)neighbors.add(id);
   if(info)netIds.add(info.net.id);
   const physical=part?.physical_pins.find(p=>p.number===number);
   return {number,name:physical?.name??number,type:physical?.electrical_type??'unspecified',side:pin.side,
    net:info?.item.name??null,neighbors:related.map(id=>comps.get(id)?.refdes??id).sort()};
  });
  return [{id:i.id,refdes:c.refdes,partId:c.part_id,pins,netCount:netIds.size,
   neighbors:[...neighbors].map(id=>comps.get(id)?.refdes??id).sort()}];
 });
 const shared=nets.filter(n=>n.localDevices>=3).sort((a,b)=>b.localDevices-a.localDevices||b.pins-a.pins||a.name.localeCompare(b.name));
 const routed=new Set(p.sheets.flatMap(s=>[...s.wires,...s.junctions,...s.splices].map(w=>w.net_id)));
 const unrouted=nets.filter(n=>n.pins>=2&&n.pins<=32&&n.externalDevices===0&&!routed.has(n.id))
  .map(({id,name,pins})=>({id,name,pins}));
 return {hubs,shared,unrouted,nets:nets.length,components:sh.instances.length};
}
