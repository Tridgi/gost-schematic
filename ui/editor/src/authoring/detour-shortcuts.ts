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
function localCrossingKeys(points:readonly ShortcutPoint[],foreign:readonly CrossingSegment[]):Set<string>{
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
 return hits;
}
export function localCrossingCount(points:readonly ShortcutPoint[],foreign:readonly CrossingSegment[]):number{
 return localCrossingKeys(points,foreign).size;
}
/** Search alternative monotone L/Z channels, not new detours.
 * Keep endpoint direction and existing lead length; caller independently
 * checks all obstacles, clearance, Net identities and actual global quality. */
export function crossingChannelShortcuts(points:readonly ShortcutPoint[],foreign:readonly CrossingSegment[],preserveStart:boolean,preserveEnd:boolean,pairedCandidate=false):[number,number][][]{
 if(points.length<3||points.length>24||foreign.length>512)return [];
 const baseline=localCrossingCount(points,foreign);
 if(!baseline&&!pairedCandidate)return [];
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
  const key=JSON.stringify(p);if(key===JSON.stringify(points)||seen.has(key))return;seen.add(key);tried++;
  const crossings=localCrossingCount(p,foreign);
  if(crossings<baseline||pairedCandidate)ranked.push({p,crossings,...m});
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


/** Candidate-only paired search. A local score is not a DRC or acceptance
 * decision: the caller must validate both changed paths on the same final
 * snapshot, then compare full layout quality and connectivity. */
export type CrossingPairWire={net:string;points:readonly ShortcutPoint[];preserveStart:boolean;preserveEnd:boolean};
type PairChoice={first:[number,number][];second:[number,number][];crossings:number;bends:number;length:number};
const asSegments=(points:readonly ShortcutPoint[],net:string):CrossingSegment[]=>
 points.slice(1).map((b,i)=>({a:points[i],b,net}));
/** Unchanged crossing keys already contribute to the global unique count.
 * Compute them once per pair, not for each Cartesian candidate. */
function fixedCrossingKeys(foreign:readonly CrossingSegment[]):Set<string>{
 const hits=new Set<string>();
 for(let i=0;i<foreign.length;i++){
  const s=foreign[i];
  for(const key of localCrossingKeys([s.a,s.b],foreign.slice(i+1))){
   const [net,x,y]=JSON.parse(key) as [string,number,number];
   hits.add(JSON.stringify([...[s.net,net].sort(),x,y]));
  }
 }
 return hits;
}
function pairCrossings(first:CrossingPairWire,second:CrossingPairWire,foreign:readonly CrossingSegment[],fixed:ReadonlySet<string>):number{
 const hits=new Set<string>();
 const add=(wire:CrossingPairWire,segments:readonly CrossingSegment[])=>{
  for(const key of localCrossingKeys(wire.points,segments)){
   const [net,x,y]=JSON.parse(key) as [string,number,number];
   const fullKey=JSON.stringify([...[wire.net,net].sort(),x,y]);
   if(!fixed.has(fullKey))hits.add(fullKey);
  }
 };
 add(first,[...foreign,...asSegments(second.points,second.net)]);
 add(second,foreign);
 return hits.size;
}
/** Rank bounded, endpoint-preserving pair candidates on their combined
 * geometry. Neither individual path may gain bends or length. */
export function rankCrossingPairs(first:CrossingPairWire,second:CrossingPairWire,
 foreign:readonly CrossingSegment[],firstChoices:readonly ShortcutPoint[][],
 secondChoices:readonly ShortcutPoint[][]):PairChoice[]{
 if(first.net===second.net||foreign.length>512||first.points.length<3||second.points.length<3||
    first.points.length>24||second.points.length>24)return [];
 const fixed=fixedCrossingKeys(foreign);
 const baseline=pairCrossings(first,second,foreign,fixed);
 if(!baseline)return [];
 const fm=pathMetric(first.points),sm=pathMetric(second.points),out:PairChoice[]=[],seen=new Set<string>();
 const usable=(wire:CrossingPairWire,raw:readonly ShortcutPoint[],old:ReturnType<typeof pathMetric>)=>{
  if(raw.length<2||raw.length>24)return null;
  const p=compact(raw);if(!p||JSON.stringify(p)===JSON.stringify(wire.points)||
   !same(p[0],wire.points[0])||!same(p.at(-1)!,wire.points.at(-1)!))return null;
  const m=pathMetric(p);
  if(m.bends>old.bends||m.length>old.length)return null;
  if(wire.preserveStart&&(!same(direction(wire.points[0],wire.points[1]) as [number,number],direction(p[0],p[1]) as [number,number])||
   pathMetric(p.slice(0,2)).length<pathMetric(wire.points.slice(0,2)).length))return null;
  if(wire.preserveEnd&&(!same(direction(wire.points.at(-2)!,wire.points.at(-1)!) as [number,number],direction(p.at(-2)!,p.at(-1)!) as [number,number])||
   pathMetric(p.slice(-2)).length<pathMetric(wire.points.slice(-2)).length))return null;
  return {p,m};
 };
 for(const a of firstChoices.slice(0,12)){
  const x=usable(first,a,fm);if(!x)continue;
  for(const b of secondChoices.slice(0,12)){
   const y=usable(second,b,sm);if(!y)continue;
   const crossings=pairCrossings({...first,points:x.p},{...second,points:y.p},foreign,fixed);
   if(crossings>=baseline)continue;
   const key=JSON.stringify([x.p,y.p]);if(seen.has(key))continue;seen.add(key);
   out.push({first:x.p,second:y.p,crossings,bends:x.m.bends+y.m.bends,length:x.m.length+y.m.length});
  }
 }
 return out.sort((a,b)=>a.crossings-b.crossings||a.bends-b.bends||a.length-b.length||
  JSON.stringify([a.first,a.second]).localeCompare(JSON.stringify([b.first,b.second]))).slice(0,12);
}
export function coordinatedCrossingShortcuts(first:CrossingPairWire,second:CrossingPairWire,
 foreign:readonly CrossingSegment[]):PairChoice[]{
 if(first.net===second.net||foreign.length>512||first.points.length<3||second.points.length<3||
  first.points.length>24||second.points.length>24)return [];
 // Include neutral individual changes: only the combined score is required
 // to improve. The single-wire API retains its strict original default.
 const choices=(wire:CrossingPairWire,partner:CrossingPairWire)=>crossingChannelShortcuts(
  wire.points,[...foreign,...asSegments(partner.points,partner.net)].filter(s=>s.net!==wire.net),
  wire.preserveStart,wire.preserveEnd,true);
 return rankCrossingPairs(first,second,foreign,choices(first,second),choices(second,first));
}


/** Visual symmetry only: adjacent parallel triples, not an electrical rule.
 * 20 mm maximum adjacent gap limits measurement to local routing corridors.
 * Weight imbalance by the common run length; require coverage not to shrink. */
export type ParallelSpacingQuality={imbalanceUm2:number;coverageUm:number;complete:boolean};
const SPACING_MAX_GAP=20000;
export function parallelSpacingQuality(segments:readonly CrossingSegment[]):ParallelSpacingQuality{
 let imbalanceUm2=0,coverageUm=0;
 if(segments.length>512)return {imbalanceUm2,coverageUm,complete:false};
 for(const axis of [0,1] as const){
  const other=axis===0?1:0;
  const events=new Map<number,{at:number;delta:number}[]>();
  const add=(x:number,at:number,delta:number)=>{
   const list=events.get(x)??[];list.push({at,delta});events.set(x,list);
  };
  for(const s of segments){
   if(s.a[other]!==s.b[other]||s.a[axis]===s.b[axis])continue;
   const lo=Math.min(s.a[axis],s.b[axis]),hi=Math.max(s.a[axis],s.b[axis]);
   add(lo,s.a[other],1);add(hi,s.a[other],-1);
  }
  const ends=[...events.keys()].sort((a,b)=>a-b),active=new Map<number,number>();
  for(let i=0;i<ends.length-1;i++){
   for(const e of events.get(ends[i])!){
    const count=(active.get(e.at)??0)+e.delta;
    if(count)active.set(e.at,count);else active.delete(e.at);
   }
   const span=ends[i+1]-ends[i],lanes=[...active.keys()].sort((a,b)=>a-b);
   for(let j=1;j<lanes.length-1;j++){
    const left=lanes[j]-lanes[j-1],right=lanes[j+1]-lanes[j];
    if(left>SPACING_MAX_GAP||right>SPACING_MAX_GAP)continue;
    coverageUm+=span;imbalanceUm2+=span*Math.abs(left-right);
   }
  }
 }
 return {imbalanceUm2,coverageUm,complete:Number.isSafeInteger(imbalanceUm2)&&Number.isSafeInteger(coverageUm)};
}

/** Move only the middle segment of a monotone Z between existing parallel
 * neighbors. No new bends, length, shortened signed leads or moved terminals.
 * Full sheet clearance, topology and quality are verified by the caller. */
export function parallelSpacingShortcuts(points:readonly ShortcutPoint[],foreign:readonly CrossingSegment[],
 preserveStart:boolean,preserveEnd:boolean):[number,number][][]{
 if(points.length<4||points.length>24||foreign.length>512)return [];
 const old=pathMetric(points),seen=new Set<string>();
 const ranked:{p:[number,number][];gain:number;span:number}[]=[];
 for(let i=0;i<points.length-3;i++){
  const [a,b,c,d]=points.slice(i,i+4);
  const axis:0|1=a[0]!==b[0]?0:1,other:0|1=axis===0?1:0;
  if(b[axis]!==c[axis]||a[other]!==b[other]||c[other]!==d[other]||
     Math.sign(b[axis]-a[axis])!==Math.sign(d[axis]-c[axis]))continue;
  const lo=Math.min(a[axis],d[axis]),hi=Math.max(a[axis],d[axis]);
  const start=Math.min(b[other],c[other]),end=Math.max(b[other],c[other]);
  const lanes=foreign.filter(s=>s.a[axis]===s.b[axis]&&s.a[other]!==s.b[other]&&
    Math.abs(s.a[axis]-b[axis])<=SPACING_MAX_GAP&&s.a[axis]!==b[axis])
   .map(s=>({at:s.a[axis],lo:Math.min(s.a[other],s.b[other]),hi:Math.max(s.a[other],s.b[other])}))
   .filter(s=>Math.min(end,s.hi)-Math.max(start,s.lo)>=10000)
   .sort((x,y)=>Math.abs(x.at-b[axis])-Math.abs(y.at-b[axis])||x.at-y.at||x.lo-y.lo||x.hi-y.hi);
  const left=lanes.filter(s=>s.at<b[axis]).slice(0,8),right=lanes.filter(s=>s.at>b[axis]).slice(0,8);
  for(const l of left)for(const r of right){
   const span=Math.min(end,l.hi,r.hi)-Math.max(start,l.lo,r.lo);
   if(span<10000)continue;
   const x=Math.round((l.at+r.at)/2);
   if(x===b[axis]||x<=lo||x>=hi||x-l.at<=1000||r.at-x<=1000)continue;
   const u:[number,number]=[b[0],b[1]],v:[number,number]=[c[0],c[1]];
   u[axis]=x;v[axis]=x;
   const p=compact([...points.slice(0,i+1),u,v,...points.slice(i+3)]);if(!p)continue;
   if(preserveStart&&(!same(direction(points[0],points[1]) as [number,number],direction(p[0],p[1]) as [number,number])||
     pathMetric(p.slice(0,2)).length<pathMetric(points.slice(0,2)).length))continue;
   if(preserveEnd&&(!same(direction(points.at(-2)!,points.at(-1)!) as [number,number],direction(p.at(-2)!,p.at(-1)!) as [number,number])||
     pathMetric(p.slice(-2)).length<pathMetric(points.slice(-2)).length))continue;
   const m=pathMetric(p);if(m.length>old.length||m.bends>old.bends)continue;
   const gain=Math.abs(2*b[axis]-l.at-r.at)-Math.abs(2*x-l.at-r.at);
   if(gain<=0)continue;
   const key=JSON.stringify(p);if(seen.has(key))continue;seen.add(key);
   ranked.push({p,gain,span});
  }
 }
 return ranked.sort((a,b)=>b.gain*b.span-a.gain*a.span||JSON.stringify(a.p).localeCompare(JSON.stringify(b.p))).slice(0,12).map(v=>v.p);
}
