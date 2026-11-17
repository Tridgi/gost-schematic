/** Native Tauri 2 close request guard. Browser navigations retain beforeunload. */
type CloseRequest={preventDefault:()=>void};
type NativeWindow={onCloseRequested:(onClose:(event:CloseRequest)=>void)=>Promise<()=>void>};
type TauriHost={
  core?:{invoke?:(command:string,args?:Record<string,unknown>)=>Promise<unknown>};
  window?:{getCurrentWindow?:()=>NativeWindow};
};
/** Return a disposer, or null in the ordinary browser; never silently fail in Tauri. */
export async function installNativeCloseGuard(
  hasUnsavedChanges:()=>boolean, confirmDiscard:()=>boolean
):Promise<(()=>void)|null>{
  if(typeof window==='undefined')return null;
  const tauri=(window as typeof window&{__TAURI__?:TauriHost}).__TAURI__;
  if(typeof tauri?.core?.invoke!=='function')return null;
  const api=tauri.window;
  if(!api||typeof api.getCurrentWindow!=='function')
    throw Error('NATIVE_CLOSE_LISTENER_UNAVAILABLE');
  return api.getCurrentWindow().onCloseRequested(event=>{
    if(hasUnsavedChanges()&&!confirmDiscard())event.preventDefault();
  });
}
