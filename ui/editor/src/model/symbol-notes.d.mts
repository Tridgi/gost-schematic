import type {ConstantAnnotation,PointUm} from './contract';
export declare function validateNotes(notes:unknown):ConstantAnnotation[];
export declare function noteLayout(note:ConstantAnnotation,at:PointUm):{baseline:PointUm;anchor:'start'|'middle'|'end';bounds:PointUm[]};
