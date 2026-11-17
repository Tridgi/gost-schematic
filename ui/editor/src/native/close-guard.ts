/** Native Tauri 2 close request guard. Browser navigations retain beforeunload. */
import {traceNativeClose} from './close-trace';
type CloseRequest={preventDefault:()=>void};
type NativeWindow={onCloseRequested:(onClose:(event:CloseRequest)=>void)=>Promise<()=>void>};
type TauriHost={
  core?:{invoke?:(command:string,args?:Record<string,unknown>)=>Promise<unknown>};
  window?:{getCurrentWindow?:()=>NativeWindow};
};
/** Return a disposer, or null in the ordinary browser; never silently fail in Tauri. */
export async function installNativeCloseGuard(
  hasUnsavedChanges:()=>boolean, confirmDiscard:()=>boolean,
  isSaveBusy:()=>boolean=()=>false
):Promise<(()=>void)|null>{
  if(typeof window==='undefined')return null;
  const tauri=(window as typeof window&{__TAURI__?:TauriHost}).__TAURI__;
  if(typeof tauri?.core?.invoke!=='function')return null;
  const api=tauri.window;
  if(!api||typeof api.getCurrentWindow!=='function')
    throw Error('NATIVE_CLOSE_LISTENER_UNAVAILABLE');
  traceNativeClose('guard_install_begin');
  const unlisten=await api.getCurrentWindow().onCloseRequested(event=>{
    const dirty=hasUnsavedChanges();
    const busy=isSaveBusy();
    traceNativeClose('guard_received',dirty,busy);
    if(!dirty&&!busy){traceNativeClose('guard_allow_clean',false,false);return;}
    const confirmed=confirmDiscard();
    traceNativeClose(confirmed?'guard_confirm_accept':'guard_confirm_cancel',dirty,busy);
    if(!confirmed){
      event.preventDefault();
      traceNativeClose('guard_prevent_default',dirty,busy);
    }
  });
  traceNativeClose('guard_subscribed');
  return ()=>{traceNativeClose('guard_unsubscribed');unlisten();};
}
