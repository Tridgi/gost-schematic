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


/** Different-Net segments only; crossings count unique Net/position pairs,
 * matching the local part of the full layout assessment. */
export type CrossingSegment={a:ShortcutPoint;b:ShortcutPoint;net:string};
export function localCrossingCount(points:readonly ShortcutPoint[],foreign:readonly CrossingSegment[]):number{
 const hits=new Set<string>();
 for(let i=1;i<points.length;i++){
  const a=points[i-1],b=points[i],horizontal=a[1]===b[1];
  for(const s of foreign){
   const other=s.a[1]===s.b[1];
   if(horizontal===other)continue;
   const h=horizontal?[a,b]:[s.a,s.b],v=horizontal?[s.a,s.b]:[a,b],x=v[0][0],y=h[0][1];
   if(x>Math.min(h[0][0],h[1][0])&&x<Math.max(h[0][0],h[1][0])&&
      y>Math.min(v[0][1],v[1][1])&&y<Math.max(v[0][1],v[1][1]))
    hits.add(JSON.stringify([s.net,x,y]));
  }
 }
 return hits.size;
}
/** Search alternative monotone L/Z channels, not new detours.
 * Keep endpoint direction and existing lead length; caller independently
 * checks all obstacles, clearance, Net identities and actual global quality. */
export function crossingChannelShortcuts(points:readonly ShortcutPoint[],foreign:readonly CrossingSegment[],preserveStart:boolean,preserveEnd:boolean):[number,number][][]{
 if(points.length<3||points.length>24||foreign.length>512)return [];
 const baseline=localCrossingCount(points,foreign);
 if(!baseline)return [];
 const old=pathMetric(points),seen=new Set<string>();
 const ranked:{p:[number,number][];crossings:number;bends:number;length:number}[]=[];
 let tried=0;
 const add=(raw:readonly ShortcutPoint[])=>{
  if(tried>=192)return;
  const p=compact(raw);if(!p)return;
  if(preserveStart&&(!same(direction(points[0],points[1]) as [number,number],direction(p[0],p[1]) as [number,number])||
     pathMetric(p.slice(0,2)).length<pathMetric(points.slice(0,2)).length))return;
  if(preserveEnd&&(!same(direction(points.at(-2)!,points.at(-1)!) as [number,number],direction(p.at(-2)!,p.at(-1)!) as [number,number])||
     pathMetric(p.slice(-2)).length<pathMetric(points.slice(-2)).length))return;
  const m=pathMetric(p);
  if(m.length>old.length||m.bends>old.bends)return;
  const key=JSON.stringify(p);if(seen.has(key))return;seen.add(key);tried++;
  const crossings=localCrossingCount(p,foreign);
  if(crossings<baseline)ranked.push({p,crossings,...m});
 };
 // Reversing the corner of an L does not change its Manhattan length.
 for(let i=0;i<points.length-2;i++){
  const [a,b,c]=points.slice(i,i+3);
  if(a[0]===c[0]||a[1]===c[1])continue;
  const corner:ShortcutPoint=a[0]===b[0]?[c[0],a[1]]:[a[0],c[1]];
  add([...points.slice(0,i+1),corner,...points.slice(i+2)]);
 }
 for(let i=0;i<points.length-3&&tried<192;i++){
  const [a,b,c,d]=points.slice(i,i+4);
  const axis:0|1=a[0]!==b[0]?0:1,other:0|1=axis===0?1:0;
  if(b[axis]!==c[axis]||a[other]!==b[other]||c[other]!==d[other]||
     Math.sign(b[axis]-a[axis])!==Math.sign(d[axis]-c[axis]))continue;
  const lo=Math.min(a[axis],d[axis]),hi=Math.max(a[axis],d[axis]);
  if(hi-lo<2002)continue;
  const values=new Set<number>([lo+1001,hi-1001,Math.round((lo+hi)/2),Math.round((3*lo+hi)/4),Math.round((lo+3*hi)/4)]);
  for(const s of foreign)for(const v of [s.a[axis],s.b[axis]])for(const delta of [-1001,1001]){
   const x=v+delta;if(x>lo&&x<hi)values.add(x);
  }
  const sorted=[...values].filter(x=>x>lo&&x<hi&&x!==b[axis]).sort((x,y)=>x-y);
  // Sample the whole channel, not only positions near its old bend.
  const selected=sorted.length<=24?sorted:Array.from({length:24},(_,j)=>sorted[Math.round(j*(sorted.length-1)/23)]);
  for(const x of selected){
   const u:[number,number]=[b[0],b[1]],v:[number,number]=[c[0],c[1]];
   u[axis]=x;v[axis]=x;
   add([...points.slice(0,i+1),u,v,...points.slice(i+3)]);
  }
 }
 return ranked.sort((a,b)=>a.crossings-b.crossings||a.bends-b.bends||a.length-b.length||
   JSON.stringify(a.p).localeCompare(JSON.stringify(b.p))).slice(0,12).map(v=>v.p);
}
