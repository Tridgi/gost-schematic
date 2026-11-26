/** Bounded local rectilinear shortcuts. Endpoints remain fixed.
 * Geometry is independently validated by the caller before any commit. */
export type ShortcutPoint=readonly [number,number];
const same=(a:ShortcutPoint,b:ShortcutPoint)=>a[0]===b[0]&&a[1]===b[1];
const direction=(a:ShortcutPoint,b:ShortcutPoint)=>[Math.sign(b[0]-a[0]),Math.sign(b[1]-a[1])];
export function pathMetric(p:readonly ShortcutPoint[]){
 let length=0,bends=0,prior:number[]|undefined;
 for(let i=1;i<p.length;i++){
  const d=direction(p[i-1],p[i]);
  length+=Math.abs(p[i][0]-p[i-1][0])+Math.abs(p[i][1]-p[i-1][1]);
  if(prior&&(d[0]!==prior[0]||d[1]!==prior[1]))bends++;
  prior=d;
 }
 return {length,bends};
}
function compact(raw:readonly ShortcutPoint[]):[number,number][]|null{
 const out:[number,number][]=[];
 for(const point of raw){
  const p:[number,number]=[point[0],point[1]];
  if(out.length&&same(out.at(-1)!,p))continue;
  if(out.length&&p[0]!==out.at(-1)![0]&&p[1]!==out.at(-1)![1])return null;
  if(out.length>=2){
   const a=direction(out.at(-2)!,out.at(-1)!),b=direction(out.at(-1)!,p);
   if(a[0]===-b[0]&&a[1]===-b[1])return null;
   if(a[0]===b[0]&&a[1]===b[1])out.pop();
  }
  out.push(p);
 }
 return out.length>=2?out:null;
}
export function detourShortcuts(points:readonly ShortcutPoint[],preserveStart:boolean,preserveEnd:boolean):[number,number][][]{
 if(points.length<3||points.length>24)return [];
 const old=pathMetric(points),seen=new Set<string>(),candidates:[number,number][][]=[];
 const add=(raw:readonly ShortcutPoint[])=>{
  const p=compact(raw);if(!p)return;
  // Existing signed physical leads are never shortened or reversed.
  if(preserveStart&&(!same(direction(points[0],points[1]) as [number,number],direction(p[0],p[1]) as [number,number])||
     pathMetric(p.slice(0,2)).length<pathMetric(points.slice(0,2)).length))return;
  if(preserveEnd&&(!same(direction(points.at(-2)!,points.at(-1)!) as [number,number],direction(p.at(-2)!,p.at(-1)!) as [number,number])||
     pathMetric(p.slice(-2)).length<pathMetric(points.slice(-2)).length))return;
  const m=pathMetric(p);
  if(m.length>old.length||m.bends>old.bends||m.length===old.length&&m.bends===old.bends)return;
  const key=JSON.stringify(p);if(seen.has(key))return;seen.add(key);candidates.push(p);
 };
 for(let i=0;i<points.length-2;i++)for(let j=i+2;j<points.length&&j-i<=6;j++){
  const a=points[i],b=points[j];
  if(a[0]===b[0]||a[1]===b[1])add([...points.slice(0,i+1),...points.slice(j)]);
  else for(const corner of [[a[0],b[1]],[b[0],a[1]]] as ShortcutPoint[])
   add([...points.slice(0,i+1),corner,...points.slice(j)]);
 }
 return candidates.sort((a,b)=>{const x=pathMetric(a),y=pathMetric(b);return x.bends-y.bends||x.length-y.length||JSON.stringify(a).localeCompare(JSON.stringify(b))}).slice(0,12);
}
