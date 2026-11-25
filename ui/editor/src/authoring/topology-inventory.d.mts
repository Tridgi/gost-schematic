import type {ProjectFileV2} from '../model/contract';
export type TopologyInventory={
 components:number;nets:number;
 unrouted:{id:string;name:string;pins:number}[];
 hubs:{id:string;refdes:string;partId:string;netCount:number;neighbors:string[];
  pins:{number:string;name:string;type:string;side:string;net:string|null;neighbors:string[]}[]}[];
 shared:{id:string;name:string;pins:number;devices:number;localDevices:number;externalDevices:number;
  powerEvidence:{refdes:string;pin:string;type:string}[]}[];
};
export function topologyInventory(file:ProjectFileV2,sheetId:string):TopologyInventory;
