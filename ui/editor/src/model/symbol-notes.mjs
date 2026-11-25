/** Constant symbol text is upright sheet ink, never a conductor or PinRef.
 * Bounds are conservative estimates, not verified font measurements. */
export function validateNotes(notes){
 if(notes===undefined)return [];
 if(!Array.isArray(notes)||notes.length>16)throw Error('INVALID_CONSTANT_ANNOTATION');
 const keys=new Set();
 for(const n of notes){
  if(!n||typeof n.key!=='string'||!n.key.length||n.key.length>64||keys.has(n.key)||
   typeof n.text!=='string'||!n.text.length||n.text.length>64||
   !Array.isArray(n.at_um)||n.at_um.length!==2||!n.at_um.every(v=>Number.isSafeInteger(v)&&Math.abs(v)<=1e9)||
   !Number.isSafeInteger(n.height_um)||n.height_um<500||n.height_um>20000||
   !['left','center','right'].includes(n.horizontal)||!['top','center','bottom'].includes(n.vertical)||
   Object.keys(n).some(k=>!['key','text','at_um','height_um','horizontal','vertical'].includes(k)))
   throw Error('INVALID_CONSTANT_ANNOTATION');
  keys.add(n.key);
 }
 return notes;
}
export function noteLayout(note,at){
 const h=note.height_um,w=(Array.from(note.text).length+1)*h;
 const x=at[0],y=at[1]+(note.vertical==='top'?h:note.vertical==='center'?Math.round(h/3):0);
 const anchor=note.horizontal==='left'?'start':note.horizontal==='right'?'end':'middle';
 const left=anchor==='start'?x-h:anchor==='end'?x-w:x-Math.ceil(w/2);
 const right=anchor==='start'?x+w:anchor==='end'?x+h:x+Math.ceil(w/2);
 return {baseline:[x,y],anchor,bounds:[[left,y-2*h],[right,y+h]]};
}
