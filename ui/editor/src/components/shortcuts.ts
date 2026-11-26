/** Safe shortcuts for a native CAD shell. Never interpret typing as a tool command. */
export type ShortcutAction = 'palette'|'export'|'save'|'saveAs'|'newProject'|'openProject'|'selectAll'|'findCatalog'|'properties'|'undo'|'redo'|'copy'|'paste'|'select'|'wire'|'pan'|'text'|'junction';
export type KeyLike = {
  key:string;ctrlKey?:boolean;metaKey?:boolean;altKey?:boolean;shiftKey?:boolean;
  repeat?:boolean;isComposing?:boolean;defaultPrevented?:boolean;
};
export function resolveShellShortcut(e:KeyLike,{editable=false,dialogOpen=false}: {editable?:boolean;dialogOpen?:boolean}={}):ShortcutAction|null {
  if(e.defaultPrevented||e.isComposing||e.repeat||e.altKey||dialogOpen) return null;
  const key=e.key.toLowerCase();
  const command=!!(e.ctrlKey||e.metaKey);
  if(command){
    if(key==='k'&&!e.shiftKey)return 'palette'; // even from a typed inspector field
    if(key==='e'&&!e.shiftKey)return 'export';
    // Don't save stale inspector drafts or undo native text edits.
    if(editable)return null;
    if(key==='s')return e.shiftKey?'saveAs':'save';
    if(key==='n'&&!e.shiftKey)return 'newProject';
    if(key==='o'&&!e.shiftKey)return 'openProject';
    if(key==='a'&&!e.shiftKey)return 'selectAll';
    if(key==='f'&&!e.shiftKey)return 'findCatalog';
    if(key==='1'&&!e.shiftKey)return 'select';
    if(key==='3'&&!e.shiftKey)return 'wire';
    if(key==='c'&&!e.shiftKey)return 'copy';
    if(key==='v'&&!e.shiftKey)return 'paste';
    if(key==='z')return e.shiftKey?'redo':'undo';
    if(key==='y'&&!e.shiftKey)return 'redo';
    return null;
  }
  if(editable||e.shiftKey)return null;
  if(key==='f2')return 'properties';
  return ({v:'select',w:'wire',h:'pan',t:'text',j:'junction'} as Record<string,ShortcutAction>)[key]??null;
}
