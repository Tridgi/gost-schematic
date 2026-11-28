/** Finite build-generated source definitions. Never infer pins from artwork. */
import type {PartDefinition,SymbolDefinition} from '../model/contract';

export type TransistorProfile={
  part_definition:PartDefinition;
  symbol_definition:SymbolDefinition;
  source_lock:{part_id:string;symbol_id:string;part_sha256:string;symbol_sha256:string;
    symbol_revision:number;symbol_status:string};
  protection:{routing_keepouts_um:readonly (readonly [number,number,number,number])[]};
};
export function stable(value:unknown):string{
  if(Array.isArray(value))return '['+value.map(stable).join(',')+']';
  if(value!==null&&typeof value==='object'){
    const record=value as Record<string,unknown>;
    return '{'+Object.keys(record).sort().map(k=>JSON.stringify(k)+':'+stable(record[k])).join(',')+'}';
  }
  return JSON.stringify(value);
}
export function lockedSymbol(profile:TransistorProfile):SymbolDefinition{
  const s=profile.symbol_definition,p=profile.part_definition,l=profile.source_lock;
  if(!s||!p||!l||s.id!=='symbol/'+p.id||s.part_id!==p.id||
     l.part_id!==p.id||l.symbol_id!==p.id||s.revision!==l.symbol_revision||
     s.status!=='draft'||l.symbol_status!=='draft'||p.reference_prefix!=='VT'||
     !/^transistor\.[a-z0-9_.]+\.layout_[vh]{2}\.(case|bare)$/.test(p.id)||
     ![l.part_sha256,l.symbol_sha256].every(x=>typeof x==='string'&&/^[a-f0-9]{64}$/.test(x))||
     !s.routing_keepouts_um?.length||stable(s.routing_keepouts_um)!==stable(profile.protection?.routing_keepouts_um))
    throw Error('TRANSISTOR_PROFILE_INVALID');
  return {...structuredClone(s),catalog_source:{part_sha256:l.part_sha256,symbol_sha256:l.symbol_sha256}};
}
export function parseTransistorManifest(raw:unknown):TransistorProfile[]{
  const m=raw as {schema_version:number;target:string;profiles:TransistorProfile[];blocked:unknown[]};
  if(m?.schema_version!==1||m.target!=='gscad-project-v2'||!Array.isArray(m.profiles)||
     m.profiles.length!==112||!Array.isArray(m.blocked)||m.blocked.length)
    throw Error('TRANSISTOR_MANIFEST_INVALID');
  const ids=new Set<string>();
  for(const p of m.profiles){
    const s=lockedSymbol(p);
    if(ids.has(s.id))throw Error('TRANSISTOR_PROFILE_DUPLICATE');
    ids.add(s.id);
  }
  return structuredClone(m.profiles);
}
export function profileFamily(p:TransistorProfile):string{
  return p.part_definition.id.split('.layout_')[0].replace('transistor.','');
}
export function profileName(p:TransistorProfile):string{
  const id=p.part_definition.id,family=profileFamily(p);
  const match=/\.layout_([vh])([vh])\.(case|bare)$/.exec(id)!;
  const title=family.replace('bjt_','BJT ').replace('mosfet_','MOSFET ')
    .replace('jfet_','JFET ').replace('igbt_','IGBT ')
    .replace('_enh',' обогащ.').replace('_dep',' обедн.')
    .replace('.body4',' BODY').replace('.body_diode',' + диод');
  const role=family.startsWith('bjt')||family.startsWith('igbt')?['C','E']:['D','S'];
  return title+' · '+role[0]+':'+(match[1]==='v'?'верт.':'гор.')+' '+role[1]+':'+
    (match[2]==='v'?'верт.':'гор.')+' · '+(match[3]==='case'?'корпус':'без корпуса');
}
