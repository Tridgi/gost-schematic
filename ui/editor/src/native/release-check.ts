/** Informational public release lookup only; never execute downloaded content. */
export const RELEASE_API='https://api.github.com/repos/Tridgi/gost-schematic/releases/latest';
export type ReleaseStatus={kind:'current'|'available'|'none';version?:string};
function stableVersion(value:unknown):number[]|null {
  if(typeof value!=='string')return null;
  const match=/^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/.exec(value);
  if(!match)return null;
  const parts=match.slice(1).map(Number);
  return parts.every(Number.isSafeInteger)?parts:null;
}
export function compareStableVersions(a:string,b:string):number {
  const x=stableVersion(a),y=stableVersion(b);
  if(!x||!y)throw Error('UNSUPPORTED_VERSION');
  for(let i=0;i<3;i++)if(x[i]!==y[i])return x[i]>y[i]?1:-1;
  return 0;
}
export function assessRelease(current:string,payload:unknown):ReleaseStatus {
  if(!payload||typeof payload!=='object')throw Error('INVALID_RELEASE');
  const r=payload as Record<string,unknown>;
  if(r.draft!==false||r.prerelease!==false||typeof r.tag_name!=='string'||!stableVersion(r.tag_name))
    throw Error('INVALID_RELEASE');
  return {kind:compareStableVersions(r.tag_name,current)>0?'available':'current',version:r.tag_name};
}
export async function checkLatestRelease(current:string,signal:AbortSignal,request:typeof fetch=fetch):Promise<ReleaseStatus>{
  const response=await request(RELEASE_API,{signal,credentials:'omit',cache:'no-store',redirect:'error',headers:{Accept:'application/vnd.github+json'}});
  if(response.status===404)return {kind:'none'}; // no public stable release, or repository inaccessible
  if(!response.ok)throw Error('RELEASE_HTTP_'+response.status);
  return assessRelease(current,await response.json());
}
