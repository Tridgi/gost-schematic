/** Source-backed DRAFT engineering artwork. Physical mm→integer µm conversion is exact.
 * Source: canonical revision-1 Python catalog definitions for the four
 * currently exposed discrete parts. These symbols remain DRAFT.
 * These symbols are NOT certified for normative ESKD printing.
 */
import type {PartDefinition, SymbolDefinition} from '../model/contract';

const pins = [
  {number:'1',name:'1',electrical_type:'passive' as const},
  {number:'2',name:'2',electrical_type:'passive' as const}
];
const diodePins = [
  {number:'1',name:'A',electrical_type:'passive' as const},
  {number:'2',name:'K',electrical_type:'passive' as const}
];
const variableResistorPins = [
  {number:'1',name:'A',electrical_type:'passive' as const},
  {number:'2',name:'B',electrical_type:'passive' as const},
  {number:'3',name:'W',electrical_type:'passive' as const}
];
export const AUTHORING_PARTS:PartDefinition[] = [
  {id:'resistor.fixed',reference_prefix:'R',symbol_ids:['symbol/resistor.fixed'],
    physical_pins:structuredClone(pins)},
  {id:'resistor.variable',reference_prefix:'R',symbol_ids:['symbol/resistor.variable'],
    physical_pins:structuredClone(variableResistorPins)},
  {id:'capacitor.fixed',reference_prefix:'C',symbol_ids:['symbol/capacitor.fixed'],
    physical_pins:structuredClone(pins)},
  {id:'diode.general',reference_prefix:'VD',symbol_ids:['symbol/diode.general'],
    physical_pins:structuredClone(diodePins)},
  {id:'fuse.general',reference_prefix:'FU',symbol_ids:['symbol/fuse.general'],
    physical_pins:structuredClone(pins)}
];
const pinDefs = [
  {physical_pin_number:'1',at_um:[-8000,0] as [number,number],side:'left' as const},
  {physical_pin_number:'2',at_um:[8000,0] as [number,number],side:'right' as const}
];
const line=(a:[number,number],b:[number,number])=>({
  kind:'line' as const,points_um:[a,b],stroke_um:300
});
export const AUTHORING_SYMBOLS:SymbolDefinition[] = [
  {
    id:'symbol/resistor.fixed',part_id:'resistor.fixed',revision:1,status:'draft',
    standard_refs:['ГОСТ 2.728-74 (requires verification before approval)'],
    pins:structuredClone(pinDefs),
    graphics:[
      {kind:'rect',points_um:[[-5000,-2000],[5000,2000]],stroke_um:300},
      line([-8000,0],[-5000,0]),line([5000,0],[8000,0])
    ]
  },
  {
    id:'symbol/resistor.variable',part_id:'resistor.variable',revision:1,status:'draft',
    standard_refs:['ГОСТ 2.728-74 (draft source geometry; physical pin numbering requires datasheet review)'],
    pins:[
      {physical_pin_number:'1',at_um:[-9000,0],side:'left'},
      {physical_pin_number:'2',at_um:[9000,0],side:'right'},
      {physical_pin_number:'3',at_um:[0,-9000],side:'top'}
    ],
    graphics:[
      {kind:'rect',points_um:[[-5000,-2000],[5000,2000]],stroke_um:300},
      line([-9000,0],[-5000,0]),line([5000,0],[9000,0]),
      line([0,-9000],[0,-2000]),
      {kind:'polyline',points_um:[[-1000,-3500],[0,-2000],[1000,-3500]],stroke_um:300}
    ]
  },
  {
    id:'symbol/capacitor.fixed',part_id:'capacitor.fixed',revision:1,status:'draft',
    standard_refs:['ГОСТ 2.728-74, таблица 4 и таблица 6 — размеры пластин требуют визуального утверждения'],
    pins:structuredClone(pinDefs),
    graphics:[
      line([-8000,0],[-750,0]),line([750,0],[8000,0]),
      line([-750,-4000],[-750,4000]),line([750,-4000],[750,4000])
    ]
  },
  {
    id:'symbol/diode.general',part_id:'diode.general',revision:1,status:'draft',
    standard_refs:['ГОСТ 2.730-73 (draft source geometry; 1:1 approval required)'],
    pins:[
      {physical_pin_number:'1',at_um:[-10000,0],side:'left'},
      {physical_pin_number:'2',at_um:[10000,0],side:'right'}
    ],
    graphics:[
      line([-10000,0],[-2500,0]),
      {kind:'polyline',points_um:[[-2500,-3000],[2500,0],[-2500,3000],[-2500,-3000]],stroke_um:300},
      line([2500,-3300],[2500,3300]),
      line([2500,0],[10000,0])
    ]
  },
  {
    id:'symbol/fuse.general',part_id:'fuse.general',revision:1,status:'draft',
    standard_refs:['ГОСТ 2.727-68 (draft source geometry; 1:1 approval required)'],
    pins:[
      {physical_pin_number:'1',at_um:[-9000,0],side:'left'},
      {physical_pin_number:'2',at_um:[9000,0],side:'right'}
    ],
    graphics:[
      line([-9000,0],[-4000,0]),
      {kind:'rect',points_um:[[-4000,-2000],[4000,2000]],stroke_um:300},
      line([4000,0],[9000,0]),
      line([-4000,0],[4000,0])
    ]
  }
];
