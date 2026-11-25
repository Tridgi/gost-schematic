/** Direct imports of canonical Python catalog JSON, no second hand-maintained geometry.
 * Circles retain exact centers and radii; all source geometry remains DRAFT.
 */
import type {PartDefinition, SymbolDefinition, PointUm, Primitive, ElectricalType} from '../model/contract';
import resistors_fixedPart from '../../../../src/gost_schematic/catalog/parts/resistors/fixed.json';
import resistors_fixedSymbol from '../../../../src/gost_schematic/catalog/symbols/resistors/fixed.json';
import resistors_variablePart from '../../../../src/gost_schematic/catalog/parts/resistors/variable.json';
import resistors_variableSymbol from '../../../../src/gost_schematic/catalog/symbols/resistors/variable.json';
import resistors_trimmerPart from '../../../../src/gost_schematic/catalog/parts/resistors/trimmer.json';
import resistors_trimmerSymbol from '../../../../src/gost_schematic/catalog/symbols/resistors/trimmer.json';
import capacitors_fixedPart from '../../../../src/gost_schematic/catalog/parts/capacitors/fixed.json';
import capacitors_fixedSymbol from '../../../../src/gost_schematic/catalog/symbols/capacitors/fixed.json';
import capacitors_polarizedPart from '../../../../src/gost_schematic/catalog/parts/capacitors/polarized.json';
import capacitors_polarizedSymbol from '../../../../src/gost_schematic/catalog/symbols/capacitors/polarized.json';
import capacitors_electrolyticPart from '../../../../src/gost_schematic/catalog/parts/capacitors/electrolytic.json';
import capacitors_electrolyticSymbol from '../../../../src/gost_schematic/catalog/symbols/capacitors/electrolytic.json';
import diodes_generalPart from '../../../../src/gost_schematic/catalog/parts/diodes/general.json';
import diodes_generalSymbol from '../../../../src/gost_schematic/catalog/symbols/diodes/general.json';
import diodes_zenerPart from '../../../../src/gost_schematic/catalog/parts/diodes/zener.json';
import diodes_zenerSymbol from '../../../../src/gost_schematic/catalog/symbols/diodes/zener.json';
import diodes_schottkyPart from '../../../../src/gost_schematic/catalog/parts/diodes/schottky.json';
import diodes_schottkySymbol from '../../../../src/gost_schematic/catalog/symbols/diodes/schottky.json';
import diodes_varicapPart from '../../../../src/gost_schematic/catalog/parts/diodes/varicap.json';
import diodes_varicapSymbol from '../../../../src/gost_schematic/catalog/symbols/diodes/varicap.json';
import diodes_ledPart from '../../../../src/gost_schematic/catalog/parts/diodes/led.json';
import diodes_ledSymbol from '../../../../src/gost_schematic/catalog/symbols/diodes/led.json';
import diodes_photodiodePart from '../../../../src/gost_schematic/catalog/parts/diodes/photodiode.json';
import diodes_photodiodeSymbol from '../../../../src/gost_schematic/catalog/symbols/diodes/photodiode.json';
import fuses_generalPart from '../../../../src/gost_schematic/catalog/parts/fuses/general.json';
import fuses_generalSymbol from '../../../../src/gost_schematic/catalog/symbols/fuses/general.json';
import transistors_bjt_npnPart from '../../../../src/gost_schematic/catalog/parts/transistors/bjt_npn.json';
import transistors_bjt_npnSymbol from '../../../../src/gost_schematic/catalog/symbols/transistors/bjt_npn.json';
import transistors_bjt_pnpPart from '../../../../src/gost_schematic/catalog/parts/transistors/bjt_pnp.json';
import transistors_bjt_pnpSymbol from '../../../../src/gost_schematic/catalog/symbols/transistors/bjt_pnp.json';
import transistors_mosfet_n_enhPart from '../../../../src/gost_schematic/catalog/parts/transistors/mosfet_n_enh.json';
import transistors_mosfet_n_enhSymbol from '../../../../src/gost_schematic/catalog/symbols/transistors/mosfet_n_enh.json';
import transistors_mosfet_p_enhPart from '../../../../src/gost_schematic/catalog/parts/transistors/mosfet_p_enh.json';
import transistors_mosfet_p_enhSymbol from '../../../../src/gost_schematic/catalog/symbols/transistors/mosfet_p_enh.json';
import transistors_bjt_npn_with_casePart from '../../../../src/gost_schematic/catalog/parts/transistors/bjt_npn_with_case.json';
import transistors_bjt_npn_with_caseSymbol from '../../../../src/gost_schematic/catalog/symbols/transistors/bjt_npn_with_case.json';
import transistors_bjt_pnp_with_casePart from '../../../../src/gost_schematic/catalog/parts/transistors/bjt_pnp_with_case.json';
import transistors_bjt_pnp_with_caseSymbol from '../../../../src/gost_schematic/catalog/symbols/transistors/bjt_pnp_with_case.json';
import transistors_mosfet_n_enh_with_casePart from '../../../../src/gost_schematic/catalog/parts/transistors/mosfet_n_enh_with_case.json';
import transistors_mosfet_n_enh_with_caseSymbol from '../../../../src/gost_schematic/catalog/symbols/transistors/mosfet_n_enh_with_case.json';
import transistors_mosfet_p_enh_with_casePart from '../../../../src/gost_schematic/catalog/parts/transistors/mosfet_p_enh_with_case.json';
import transistors_mosfet_p_enh_with_caseSymbol from '../../../../src/gost_schematic/catalog/symbols/transistors/mosfet_p_enh_with_case.json';

type SourcePart={id:string;reference_prefix:string;symbol_id:string;nominal_kind:string|null;pins:{number:string;name:string;electrical_type:string}[]};
type SourceSymbol={id:string;revision:number;status:string;standard_refs:string[];line_width_mm:number;
 pins:{number:string;at_mm:number[];side:string}[];
 geometry:{rectangles:number[][];lines:number[][][];circles:{center_mm:number[];radius_mm:number}[]}};
type Entry={part:SourcePart;symbol:SourceSymbol;name:string;category:string};
const entries:Entry[]=[
  {part:resistors_fixedPart,symbol:resistors_fixedSymbol,name:"Резистор постоянный",category:"Резисторы"},
  {part:resistors_variablePart,symbol:resistors_variableSymbol,name:"Резистор переменный",category:"Резисторы"},
  {part:resistors_trimmerPart,symbol:resistors_trimmerSymbol,name:"Резистор подстроечный",category:"Резисторы"},
  {part:capacitors_fixedPart,symbol:capacitors_fixedSymbol,name:"Конденсатор неполярный",category:"Конденсаторы"},
  {part:capacitors_polarizedPart,symbol:capacitors_polarizedSymbol,name:"Конденсатор поляризованный",category:"Конденсаторы"},
  {part:capacitors_electrolyticPart,symbol:capacitors_electrolyticSymbol,name:"Конденсатор электролитический",category:"Конденсаторы"},
  {part:diodes_generalPart,symbol:diodes_generalSymbol,name:"Диод общий",category:"Диоды"},
  {part:diodes_zenerPart,symbol:diodes_zenerSymbol,name:"Стабилитрон",category:"Диоды"},
  {part:diodes_schottkyPart,symbol:diodes_schottkySymbol,name:"Диод Шоттки",category:"Диоды"},
  {part:diodes_varicapPart,symbol:diodes_varicapSymbol,name:"Варикап",category:"Диоды"},
  {part:diodes_ledPart,symbol:diodes_ledSymbol,name:"Светодиод",category:"Диоды"},
  {part:diodes_photodiodePart,symbol:diodes_photodiodeSymbol,name:"Фотодиод",category:"Диоды"},
  {part:fuses_generalPart,symbol:fuses_generalSymbol,name:"Предохранитель плавкий",category:"Предохранители"},
  {part:transistors_bjt_npnPart,symbol:transistors_bjt_npnSymbol,name:"Транзистор NPN",category:"Транзисторы"},
  {part:transistors_bjt_pnpPart,symbol:transistors_bjt_pnpSymbol,name:"Транзистор PNP",category:"Транзисторы"},
  {part:transistors_mosfet_n_enhPart,symbol:transistors_mosfet_n_enhSymbol,name:"MOSFET N-канальный",category:"Транзисторы"},
  {part:transistors_mosfet_p_enhPart,symbol:transistors_mosfet_p_enhSymbol,name:"MOSFET P-канальный",category:"Транзисторы"},
  {part:transistors_bjt_npn_with_casePart,symbol:transistors_bjt_npn_with_caseSymbol,name:"Транзистор NPN с корпусом",category:"Транзисторы"},
  {part:transistors_bjt_pnp_with_casePart,symbol:transistors_bjt_pnp_with_caseSymbol,name:"Транзистор PNP с корпусом",category:"Транзисторы"},
  {part:transistors_mosfet_n_enh_with_casePart,symbol:transistors_mosfet_n_enh_with_caseSymbol,name:"MOSFET N-канальный с корпусом",category:"Транзисторы"},
  {part:transistors_mosfet_p_enh_with_casePart,symbol:transistors_mosfet_p_enh_with_caseSymbol,name:"MOSFET P-канальный с корпусом",category:"Транзисторы"}
];
const electricalTypes=new Set<string>(['passive','input','output','bidirectional','power_input','power_output','open_collector','unspecified']);
const sides=new Set<string>(['left','right','top','bottom']);
function mm(n:number):number {
 const um=Math.round(n*1000);
 if(!Number.isSafeInteger(um)||Math.abs(n*1000-um)>1e-6)throw Error('CATALOG_NON_INTEGER_UM');
 return um;
}
function point(p:number[]):PointUm {
 if(p.length!==2)throw Error('CATALOG_INVALID_POINT');
 return [mm(p[0]),mm(p[1])];
}
function convert(entry:Entry):{part:PartDefinition;symbol:SymbolDefinition}{
 const {part:p,symbol:s}=entry;
 if(p.symbol_id!==s.id||s.status!=='draft')throw Error('CATALOG_SOURCE_MISMATCH: '+s.id);
 const id='symbol/'+s.id,stroke=mm(s.line_width_mm);
 const physical=p.pins.map(pin=>{
  if(!electricalTypes.has(pin.electrical_type))throw Error('CATALOG_ELECTRICAL_TYPE');
  return {number:pin.number,name:pin.name,electrical_type:pin.electrical_type as ElectricalType};
 });
 const pins=s.pins.map(pin=>{
  if(!sides.has(pin.side)||!physical.some(p=>p.number===pin.number))throw Error('CATALOG_PIN_MISMATCH');
  return {physical_pin_number:pin.number,at_um:point(pin.at_mm),side:pin.side as SymbolDefinition['pins'][number]['side']};
 });
 if(new Set(pins.map(p=>p.physical_pin_number)).size!==physical.length||pins.length!==physical.length)
  throw Error('CATALOG_PIN_COUNT');
 const graphics:Primitive[]=[
  ...s.geometry.rectangles.map((r):Primitive=>({kind:'rect',points_um:[point(r.slice(0,2)),point(r.slice(2))],stroke_um:stroke})),
  ...s.geometry.lines.map((l):Primitive=>({kind:'line',points_um:l.map(point),stroke_um:stroke}))
 ];
 for(const circle of s.geometry.circles){
  const [x,y]=point(circle.center_mm),r=mm(circle.radius_mm);
  graphics.push({kind:'circle',points_um:[[x,y],[x+r,y]],stroke_um:stroke});
 }
 return {
  part:{id:p.id,reference_prefix:p.reference_prefix,symbol_ids:[id],physical_pins:physical},
  symbol:{id,part_id:p.id,revision:s.revision,status:'draft',pins,graphics,
   standard_refs:[...s.standard_refs]}
 };
}
const converted=entries.map(convert);
export const AUTHORING_PARTS:PartDefinition[]=converted.map(x=>x.part);
export const AUTHORING_SYMBOLS:SymbolDefinition[]=converted.map(x=>x.symbol);
const metadata=new Map(entries.map(e=>['symbol/'+e.symbol.id,e]));
export function catalogDisplay(id:string):{name:string;category:string}|undefined {
 const e=metadata.get(id);return e?{name:e.name,category:e.category}:undefined;
}
export function catalogDefaultValue(partId:string):string {
 const e=entries.find(x=>x.part.id===partId);
 return e?.part.nominal_kind==='resistance'?'1к':e?.part.nominal_kind==='capacitance'?'100н':'';
}

/** Add only pairs absent from a saved synthetic project's immutable library.
 * Existing part/symbol IDs (even custom or older revisions) are never replaced. */
export function catalogAdditions(parts:readonly PartDefinition[],symbols:readonly SymbolDefinition[]){
 const partIds=new Set(parts.map(p=>p.id)),symbolIds=new Set(symbols.map(s=>s.id));
 return converted.filter(x=>!partIds.has(x.part.id)&&!symbolIds.has(x.symbol.id));
}
