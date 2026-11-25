import type {PointUm} from './contract';
export declare function curveGeometry(kind:'circle'|'semicircle',pts:readonly PointUm[]):{center:PointUm;radius:number;sweep:0|1;bounds:PointUm[]};
export declare function curveChords(kind:'circle'|'semicircle',pts:readonly PointUm[]):{from_um:[number,number];to_um:[number,number]}[];
