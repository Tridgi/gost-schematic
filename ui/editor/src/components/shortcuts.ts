/** Safe shortcuts for a native CAD shell. Never interpret typing as a tool command. */
export type ShortcutAction = 'palette'|'export'|'save'|'undo'|'redo'|'select'|'wire'|'pan'|'text';
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
    if(key==='s'&&!e.shiftKey)return 'save';
    if(key==='z')return e.shiftKey?'redo':'undo';
    if(key==='y'&&!e.shiftKey)return 'redo';
    return null;
  }
  if(editable||e.shiftKey)return null;
  return ({v:'select',w:'wire',h:'pan',t:'text'} as Record<string,ShortcutAction>)[key]??null;
}
