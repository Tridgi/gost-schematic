import type {ProjectFileV2} from '../model/contract';
import type {CanvasScene} from '../canvas/scene-projection.mjs';
import type {WiringSnapshot} from '../wires/manual-wire';
export type Diagnostic={id:string;code:string;severity:'error'|'warning'|'info';message:string;instanceId?:string};
export declare function analyzeDiagnostics(file:ProjectFileV2,scene:CanvasScene,snapshot:WiringSnapshot,routeStatuses?:Record<string,string>,options?:{maxItems?:number;maxComparisons?:number}):{items:Diagnostic[];counts:{error:number;warning:number;info:number};comparisons:number;incomplete:boolean;omitted:number};
