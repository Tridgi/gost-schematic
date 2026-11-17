/** Opt-in, fixed-field native lifecycle telemetry. Rust drops it without GSCAD_R6_TRACE_WINDOW=1. */
export type NativeCloseStage =
  | 'guard_install_begin' | 'guard_subscribed' | 'guard_unsubscribed'
  | 'guard_received' | 'guard_allow_clean' | 'guard_confirm_accept'
  | 'guard_confirm_cancel' | 'guard_prevent_default'
  | 'app_effect_mounted' | 'app_effect_unmounted' | 'browser_beforeunload';

export function traceNativeClose(stage:NativeCloseStage,dirty=false,busy=false):void {
  if(typeof window==='undefined')return;
  const host=window as typeof window&{
    __TAURI__?:{core?:{invoke?:(command:string,args:Record<string,unknown>)=>Promise<unknown>}}
  };
  const invoke=host.__TAURI__?.core?.invoke;
  if(typeof invoke!=='function')return;
  // The trace contains neither user project data nor file names or paths.
  void invoke('native_close_trace',{stage,dirty,busy}).catch(()=>{});
}
