/**
 * Read-only projection of a schema-validated gscad-project v2 into CHAT5 shell DTOs.
 * No Canvas pixels or visual crossing may create electrical Net membership.
 */
export type PinRefView = {component_id:string;physical_pin_number:string};
export type PartView = {id:string;physical_pins:readonly {number:string}[]};
export type ComponentView = {id:string;refdes:string;value:string;part_id:string};
export type NetView = {id:string;name:string;members:readonly PinRefView[];route_status:'unrouted'|'partial'|'verified'};
export type InstanceView = {id:string;component_id:string;origin_um:readonly [number,number];rotation_deg:0|90|180|270};
export type SheetView = {id:string;name:string;instances:readonly InstanceView[];wires:readonly {id:string;net_id:string}[];graphics:readonly {id:string;kind:string}[]};
export type ProjectViewInput = {
  format:'gscad-project';format_version:2;
  project:{title:string;part_definitions:readonly PartView[];components:readonly ComponentView[];nets:readonly NetView[];sheets:readonly SheetView[]};
  workspace:{active_sheet_id:string};
};
export type TreeRowView = {id:string;label:string;kind:'sheet'|'instance'|'net'|'wire'|'graphic';indent:number};
export type InspectorView = {
  id:string;refdes:string;value:string;originUm:readonly [number,number];rotationDeg:0|90|180|270;
  physicalPins:readonly {number:string;netName:string|null}[];
};
export type ShellProjectView = {projectName:string;activeSheetId:string;sheets:readonly {id:string;title:string}[];tree:readonly TreeRowView[];selected:InspectorView|null};

function fail(code:string):never {throw new Error(code);}
function byId<T extends {id:string}>(items:readonly T[],code:string):Map<string,T> {
  const out=new Map<string,T>();
  for(const item of items){
    if(!item||typeof item.id!=='string'||!item.id.trim()||out.has(item.id))fail(code);
    out.set(item.id,item);
  }
  return out;
}
function indexMemberships(nets:readonly NetView[]):Map<string,Map<string,string>>{
  const owners=new Map<string,Map<string,string>>();
  const seenNets=new Set<string>();
  for(const net of nets){
    if(!net.id||seenNets.has(net.id)||!Array.isArray(net.members))fail('INVALID_NET');
    seenNets.add(net.id);
    for(const pin of net.members){
      if(!pin||!pin.component_id||!pin.physical_pin_number)fail('INVALID_PINREF');
      let component=owners.get(pin.component_id);
      if(!component){component=new Map();owners.set(pin.component_id,component);}
      if(component.has(pin.physical_pin_number))fail('DUPLICATE_PIN_MEMBERSHIP');
      component.set(pin.physical_pin_number,net.name);
    }
  }
  return owners;
}
/** Validate the project at its authoritative model boundary first; this is UI projection, not schema validation. */
export function projectToShellView(file:ProjectViewInput,selectedInstanceId:string|null=null):ShellProjectView{
  if(file?.format!=='gscad-project'||file.format_version!==2)fail('UNSUPPORTED_PROJECT_V2');
  const p=file.project;
  if(!p||!Array.isArray(p.components)||!Array.isArray(p.part_definitions)||!Array.isArray(p.nets)||!Array.isArray(p.sheets))fail('INVALID_PROJECT_COLLECTIONS');
  const components=byId<ComponentView>(p.components,'INVALID_COMPONENT_ID');
  const parts=byId<PartView>(p.part_definitions,'INVALID_PART_ID');
  const sheets=byId<SheetView>(p.sheets,'INVALID_SHEET_ID');
  const active=sheets.get(file.workspace?.active_sheet_id);
  if(!active)fail('UNKNOWN_ACTIVE_SHEET');
  const memberships=indexMemberships(p.nets);
  // Fail closed even without a selection: source Nets cannot refer to foreign or absent pins.
  for(const component of p.components){
    const part=parts.get(component.part_id);
    if(!part||!Array.isArray(part.physical_pins))fail('UNKNOWN_PART_DEFINITION');
    const known=new Set(part.physical_pins.map(pin=>pin.number));
    if(known.size!==part.physical_pins.length||known.has(''))fail('DUPLICATE_PHYSICAL_PIN');
    for(const number of memberships.get(component.id)?.keys()??[])
      if(!known.has(number))fail('UNKNOWN_PHYSICAL_PIN');
  }
  for(const id of memberships.keys())if(!components.has(id))fail('UNKNOWN_COMPONENT_PINREF');
  const tree:TreeRowView[]=[];
  const instanceIndex=new Map<string,InstanceView>();
  for(const sheet of p.sheets){
    if(!Array.isArray(sheet.instances)||!Array.isArray(sheet.wires)||!Array.isArray(sheet.graphics))fail('INVALID_SHEET_COLLECTIONS');
    tree.push({id:'sheet:'+sheet.id,label:sheet.name,kind:'sheet',indent:0});
    for(const instance of sheet.instances){
      if(instanceIndex.has(instance.id))fail('DUPLICATE_INSTANCE_ID');
      instanceIndex.set(instance.id,instance);
      const component=components.get(instance.component_id);
      if(!component)fail('UNKNOWN_COMPONENT');
      tree.push({id:'instance:'+instance.id,label:component.refdes+' · '+component.value,kind:'instance',indent:1});
    }
    for(const wire of sheet.wires)tree.push({id:'wire:'+sheet.id+':'+wire.id,label:'Провод '+wire.id,kind:'wire',indent:1});
    for(const graphic of sheet.graphics){
      tree.push({id:'graphic:'+sheet.id+':'+graphic.id,label:graphic.kind==='source_b_continuation'?'b · графика, не Net':'Графика '+graphic.id,kind:'graphic',indent:1});
    }
  }
  // Nets are source-declared, NOT inferred from the displayed wire geometry.
  for(const net of p.nets)tree.push({id:'net:'+net.id,label:net.name+' · '+net.route_status,kind:'net',indent:0});
  let selected:InspectorView|null=null;
  if(selectedInstanceId!==null){
    const instance=active.instances.find(item=>item.id===selectedInstanceId);
    if(!instance)fail('UNKNOWN_SELECTED_INSTANCE');
    const component=components.get(instance.component_id);
    if(!component)fail('UNKNOWN_COMPONENT');
    const part=parts.get(component.part_id);
    if(!part||!Array.isArray(part.physical_pins))fail('UNKNOWN_PART_DEFINITION');
    const pinNumbers=new Set<string>();
    const assigned=memberships.get(component.id);
    const physicalPins=(part.physical_pins as readonly {number:string}[]).map(pin=>{
      if(!pin.number||pinNumbers.has(pin.number))fail('DUPLICATE_PHYSICAL_PIN');
      pinNumbers.add(pin.number);
      return {number:pin.number,netName:assigned?.get(pin.number)??null};
    });
    if(assigned&&[...assigned.keys()].some(n=>!pinNumbers.has(n)))fail('UNKNOWN_PHYSICAL_PIN');
    if(instance.origin_um.length!==2||instance.origin_um.some(x=>!Number.isSafeInteger(x)||Math.abs(x)>1_000_000_000))fail('INVALID_UM_POINT');
    if(!([0,90,180,270] as number[]).includes(instance.rotation_deg))fail('INVALID_ROTATION');
    selected={id:instance.id,refdes:component.refdes,value:component.value,originUm:[...instance.origin_um] as [number,number],rotationDeg:instance.rotation_deg,physicalPins};
  }
  return {projectName:p.title,activeSheetId:active.id,sheets:p.sheets.map(s=>({id:s.id,title:s.name})),tree,selected};
}
