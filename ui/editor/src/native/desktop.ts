/** Tauri-only allowlisted commands; the host never accepts JavaScript file paths.
 * withGlobalTauri is configured in ui/desktop/src-tauri/tauri.conf.json.
 * Browser build has no dependency on Tauri APIs and retains JSON downloads.
 */
import type {ProjectFileV2} from '../model/contract';

export type NativeDocumentHandle = {
  handle:string;
  generation:number;
  project_sha256:string;
  filename:string;
};
export type NativeDocumentReply = NativeDocumentHandle & {document:ProjectFileV2};

type Invoke = <T>(command:string,args?:Record<string,unknown>)=>Promise<T>;
function host():Invoke|null {
  if(typeof window==='undefined')return null;
  const target=window as typeof window & {
    __TAURI__?:{core?:{invoke?:Invoke}}
  };
  return target.__TAURI__?.core?.invoke??null;
}
export function nativeDesktopAvailable():boolean {
  return host()!==null;
}
export function nativeOpenProject():Promise<NativeDocumentReply>{
  const invoke=host();if(!invoke)throw Error('NATIVE_HOST_UNAVAILABLE');
  return invoke('native_open_project');
}
export function nativeSaveProject(
  previous:NativeDocumentHandle,
  document:ProjectFileV2
):Promise<NativeDocumentReply>{
  const invoke=host();if(!invoke)throw Error('NATIVE_HOST_UNAVAILABLE');
  return invoke('native_save_project',{
    handle:previous.handle,expectedGeneration:previous.generation,
    expectedProjectSha256:previous.project_sha256,document
  });
}
export function nativeSaveAsProject(
  document:ProjectFileV2,previous:NativeDocumentHandle|null
):Promise<NativeDocumentReply>{
  const invoke=host();if(!invoke)throw Error('NATIVE_HOST_UNAVAILABLE');
  return invoke('native_save_as_project',{
    document,previousHandle:previous?.handle??null,
    expectedGeneration:previous?.generation??null,
    expectedProjectSha256:previous?.project_sha256??null
  });
}
export async function nativeCloseProject(handle:string):Promise<void>{
  const invoke=host();if(!invoke)return;
  await invoke('native_close_project',{handle});
}

/** Python canonical v2 exporter -> verified bytes -> OS native save dialog.
 * No path leaves Rust. This is an explicitly UNVERIFIED-FONT engineering preview.
 */
export async function nativeExportProject(
  document:ProjectFileV2,sheetId:string,format:'svg'|'png300'
):Promise<string>{
  const invoke=host();if(!invoke)throw Error('NATIVE_HOST_UNAVAILABLE');
  return invoke('native_export_project',{document,sheetId,format});
}

export type ProjectLink='founder'|'repository'|'releases';
export async function nativeAppVersion():Promise<string>{
  const invoke=host();if(!invoke)throw Error('NATIVE_HOST_UNAVAILABLE');
  return invoke('native_app_version');
}
export async function nativeOpenProjectLink(link:ProjectLink):Promise<void>{
  const invoke=host();if(!invoke)throw Error('NATIVE_HOST_UNAVAILABLE');
  return invoke('native_open_project_link',{link});
}

export type SignedUpdateStatus={kind:'idle'}|{kind:'downloading';received:number;total:number|null}|{kind:'ready';version:string;token:string}|{kind:'installing'};
async function invokeUpdate<T>(command:string,args?:Record<string,unknown>):Promise<T>{
  const invoke=host();if(!invoke)throw Error('NATIVE_HOST_UNAVAILABLE');
  return invoke<T>(command,args);
}
export const nativeSignedUpdateEnabled=()=>invokeUpdate<boolean>('native_signed_update_enabled');
export const nativeSignedUpdateStatus=()=>invokeUpdate<SignedUpdateStatus>('native_signed_update_status');
export const nativePrepareSignedUpdate=(version:string)=>invokeUpdate<void>('native_prepare_signed_update',{version});
export const nativeDiscardSignedUpdate=()=>invokeUpdate<void>('native_discard_signed_update');
export const nativeInstallSignedUpdate=(token:string,projectSafe:boolean)=>invokeUpdate<void>('native_install_signed_update',{token,projectSafe});
