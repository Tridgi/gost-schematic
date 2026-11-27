/** Bounded rectilinear visibility-grid tree heuristic.
 * Obstacles are closed, integer envelopes already inflated by caller.
 * Pin leads are immutable signed segments; only their outer tips may attach.
 * Grow a tree by shortest multi-source paths, then collapse degree-2 chains.
 * No claim of minimum Steiner tree or completeness outside this finite grid. */
export type TreePoint=[number,number];
export type TreeBox={minX:number;minY:number;maxX:number;maxY:number};
export type TreePort={pin:TreePoint;tip:TreePoint};
export type TreePath={points:TreePoint[];startPin:number|null;endPin:number|null};
export type TreePlan={paths:TreePath[];nodes:TreePoint[];lengthUm:number;bends:number};
/** Finite deterministic alternatives; default preserves the established route. */
export type TreeStrategy='default'|'crossing-first'|'bend-first'|'peripheral-root';
export type TreeCrossable={a:TreePoint;b:TreePoint;clearance:number};
type Edge={to:number;length:number;dir:1|2;crossings:number};
const key=(p:TreePoint)=>p.join(',');
const eq=(a:TreePoint,b:TreePoint)=>a[0]===b[0]&&a[1]===b[1];
const box=(a:TreePoint,b:TreePoint):TreeBox=>({minX:Math.min(a[0],b[0]),maxX:Math.max(a[0],b[0]),minY:Math.min(a[1],b[1]),maxY:Math.max(a[1],b[1])});
const overlaps=(a:TreeBox,b:TreeBox)=>a.minX<=b.maxX&&b.minX<=a.maxX&&a.minY<=b.maxY&&b.minY<=a.maxY;
const length=(a:TreePoint,b:TreePoint)=>Math.abs(a[0]-b[0])+Math.abs(a[1]-b[1]);
class Heap{
 private a:{state:number;cost:number}[]=[];
 push(v:{state:number;cost:number}){let i=this.a.length;this.a.push(v);while(i){const p=(i-1)>>1;if(this.a[p].cost<=v.cost)break;this.a[i]=this.a[p];i=p}this.a[i]=v}
 pop(){const a=this.a,first=a[0],last=a.pop();if(!last||!a.length)return first;let i=0;while(i*2+1<a.length){let c=i*2+1;if(c+1<a.length&&a[c+1].cost<a[c].cost)c++;if(a[c].cost>=last.cost)break;a[i]=a[c];i=c}a[i]=last;return first}
 get size(){return this.a.length}
}
/** Keep every terminal coordinate and frame edge; thin optional obstacle
 * channels by splitting the largest remaining coordinate gap. Geometry
 * predicates still test every obstacle, so thinning cannot permit a collision. */
function thinAxis(all:number[],mandatory:Set<number>,limit:number):number[]{
 if(all.length<=limit)return all;
 const selected=new Set(all.filter(v=>mandatory.has(v)));
 if(selected.size>limit)throw Error('TREE_GRID_LIMIT');
 while(selected.size<limit&&selected.size<all.length){
  const sorted=[...selected].sort((a,b)=>a-b);
  let best:number|undefined,bestGap=-1;
  for(let i=1;i<sorted.length;i++){
   const lo=sorted[i-1],hi=sorted[i],mid=(lo+hi)/2;
   const values=all.filter(v=>v>lo&&v<hi);
   if(!values.length||hi-lo<=bestGap)continue;
   bestGap=hi-lo;best=values.reduce((a,b)=>Math.abs(a-mid)<=Math.abs(b-mid)?a:b);
  }
  if(best===undefined)break;selected.add(best);
 }
 return [...selected].sort((a,b)=>a-b);
}
export function planOrthogonalTree(ports:TreePort[],obstacles:TreeBox[],frame:TreeBox,crossable:TreeCrossable[]=[],adaptiveGrid=false,strategy:TreeStrategy='default'):TreePlan|null{
 if(ports.length<2||ports.length>32||obstacles.length+crossable.length>640)return null;
 const inside=(p:TreePoint)=>p[0]>=frame.minX&&p[0]<=frame.maxX&&p[1]>=frame.minY&&p[1]<=frame.maxY;
 const stubs=ports.map(p=>box(p.pin,p.tip));
 if(ports.some(p=>!inside(p.tip)||!inside(p.pin)||eq(p.pin,p.tip)||(p.pin[0]!==p.tip[0]&&p.pin[1]!==p.tip[1])))return null;
 if(stubs.some((b,i)=>stubs.slice(i+1).some(c=>overlaps(b,c))))return null;
 const crossBoxes=crossable.map(w=>{
  const b=box(w.a,w.b),p=w.clearance;
  if(!Number.isSafeInteger(p)||p<1||eq(w.a,w.b)||(w.a[0]!==w.b[0]&&w.a[1]!==w.b[1]))throw Error('TREE_INVALID_CROSSABLE');
  return {w,b:{minX:b.minX-p,minY:b.minY-p,maxX:b.maxX+p,maxY:b.maxY+p}};
 });
 let comparisons=0;
 const clear=(a:TreePoint,b:TreePoint)=>{
  const segment=box(a,b);
  for(const o of obstacles){if(++comparisons>3000000)throw Error('TREE_SEARCH_LIMIT');if(overlaps(segment,o))return false}
  for(const {w,b:obstacle} of crossBoxes){
   if(++comparisons>3000000)throw Error('TREE_SEARCH_LIMIT');
   if(!overlaps(segment,obstacle))continue;
   // No search vertex, bend, branch or terminal inside the foreign
   // keepout. Only a perpendicular edge spanning its full width may pass.
   if(eq(a,b))return false;
   const horizontal=a[1]===b[1],other=w.a[1]===w.b[1];
   if(horizontal===other)return false;
   const fixed=horizontal?1:0,variable=1-fixed,at=a[fixed];
   if(at<=Math.min(w.a[fixed],w.b[fixed])+w.clearance||
      at>=Math.max(w.a[fixed],w.b[fixed])-w.clearance)return false;
   const low=variable===0?obstacle.minX:obstacle.minY,high=variable===0?obstacle.maxX:obstacle.maxY;
   if(Math.min(a[variable],b[variable])>=low||Math.max(a[variable],b[variable])<=high)return false;
  }
  for(const [i,s] of stubs.entries()){
   if(++comparisons>3000000)throw Error('TREE_SEARCH_LIMIT');
   if(!overlaps(segment,s))continue;
   const tip=ports[i].tip;
   if(!(eq(a,tip)||eq(b,tip))||Math.max(segment.minX,s.minX)!==Math.min(segment.maxX,s.maxX)||
    Math.max(segment.minY,s.minY)!==Math.min(segment.maxY,s.maxY))return false;
  }
  return true;
 };
 const xs=new Set([frame.minX,frame.maxX]),ys=new Set([frame.minY,frame.maxY]);
 for(const {tip} of ports){xs.add(tip[0]);ys.add(tip[1])}
 for(const b of [...obstacles,...crossBoxes.map(v=>v.b),...stubs]){
  xs.add(Math.floor(b.minX)-1);xs.add(Math.ceil(b.maxX)+1);
  ys.add(Math.floor(b.minY)-1);ys.add(Math.ceil(b.maxY)+1);
 }
 let X=[...xs].filter(x=>x>=frame.minX&&x<=frame.maxX).sort((a,b)=>a-b);
 let Y=[...ys].filter(y=>y>=frame.minY&&y<=frame.maxY).sort((a,b)=>a-b);
 if(adaptiveGrid){
  const mx=new Set([frame.minX,frame.maxX,...ports.map(p=>p.tip[0])]);
  const my=new Set([frame.minY,frame.maxY,...ports.map(p=>p.tip[1])]);
  // Each vertex and its at most two forward visibility edges are
  // checked against all keepouts. Reserve headroom for the hard cap.
  const budget=Math.min(6500,Math.floor(2700000/(3*Math.max(1,obstacles.length+crossable.length+stubs.length))));
  let nx=Math.min(96,X.length),ny=Math.min(96,Y.length);
  while(nx*ny>budget){
   const canX=nx>mx.size,canY=ny>my.size;
   if(!canX&&!canY)throw Error('TREE_GRID_LIMIT');
   if(canX&&(!canY||nx/mx.size>=ny/my.size))nx--;else ny--;
  }
  X=thinAxis(X,mx,nx);Y=thinAxis(Y,my,ny);
 }
 if(X.length>96||Y.length>96||X.length*Y.length>6500)throw Error('TREE_GRID_LIMIT');
 const points:TreePoint[]=[],indices=new Map<string,number>(),edges:Edge[][]=[];
 const node=(p:TreePoint)=>indices.get(key(p));
 for(const y of Y)for(const x of X){
  const p:TreePoint=[x,y];if(!clear(p,p))continue;
  indices.set(key(p),points.length);points.push(p);edges.push([]);
 }
 const join=(a:TreePoint,b:TreePoint,dir:1|2)=>{
  const i=node(a),j=node(b);if(i===undefined||j===undefined||!clear(a,b))return;
  const len=length(a,b),crossings=crossBoxes.filter(v=>overlaps(box(a,b),v.b)).length;
  edges[i].push({to:j,length:len,dir,crossings});edges[j].push({to:i,length:len,dir,crossings});
 };
 // Join consecutive available vertices, skipping blocked grid points only
 // if the entire segment passes the same obstacle/lead/crossing checks.
 if(!crossable.length){
  for(const y of Y)for(let x=1;x<X.length;x++)join([X[x-1],y],[X[x],y],1);
  for(const x of X)for(let y=1;y<Y.length;y++)join([x,Y[y-1]],[x,Y[y]],2);
 }else{
 for(const y of Y){let prev:TreePoint|undefined;for(const x of X){
  const p:TreePoint=[x,y];if(node(p)===undefined)continue;
  if(prev)join(prev,p,1);prev=p;
 }}
 for(const x of X){let prev:TreePoint|undefined;for(const y of Y){
  const p:TreePoint=[x,y];if(node(p)===undefined)continue;
  if(prev)join(prev,p,2);prev=p;
 }}
 }
 const terminals=ports.map(p=>node(p.tip));
 if(terminals.some(v=>v===undefined))return null;
 const leadDir=new Map(terminals.map((v,i)=>[v!,ports[i].pin[0]===ports[i].tip[0]?2:1]));
 // Different objectives and a different first terminal expose distinct
 // greedy trees without modifying the physical port order or keepouts.
 const bendCost=strategy==='bend-first'?15000:5000;
 const crossingCost=strategy==='crossing-first'?60000:20000;
 let rootIndex=0;
 if(strategy==='bend-first'||strategy==='peripheral-root'){
  const spans=ports.map(p=>ports.reduce((n,q)=>n+length(p.tip,q.tip),0));
  for(let i=1;i<ports.length;i++){
   if(strategy==='bend-first'?spans[i]<spans[rootIndex]:spans[i]>spans[rootIndex])rootIndex=i;
  }
 }
 const grow=(respectLeads:boolean):TreePlan|null=>{
 const remaining=new Set(terminals as number[]),root=terminals[rootIndex]!;
 const tree=new Set<number>([root]),adj=new Map<number,Set<number>>();
 remaining.delete(root);
 const link=(a:number,b:number)=>{const add=(x:number,y:number)=>{const s=adj.get(x)??new Set<number>();s.add(y);adj.set(x,s)};add(a,b);add(b,a)};
 while(remaining.size){
  const dist=new Float64Array(points.length*3).fill(Infinity),prev=new Int32Array(points.length*3).fill(-1),heap=new Heap();
  // Only the initial isolated root has a mandatory incoming lead. Later
  // attachments are junctions, so their previous axis is not prescribed.
  for(const v of tree){const state=v*3+(respectLeads&&tree.size===1?leadDir.get(v)!:0);dist[state]=0;heap.push({state,cost:0})}
  let goal=-1,bestGoal=Infinity;
  while(heap.size){
   const {state,cost}=heap.pop();if(cost!==dist[state])continue;
   if(cost>=bestGoal)break;
   const v=Math.floor(state/3),dir=state%3;
   if(remaining.has(v)){
    if(!respectLeads){goal=state;break}
    const score=cost+(dir!==leadDir.get(v)?bendCost:0);
    if(score<bestGoal){goal=state;bestGoal=score}
    // Never pass through an unattached physical terminal to reach another.
    continue;
   }
   for(const e of edges[v]){
    if(tree.has(e.to))continue;
    const next=e.to*3+e.dir,score=cost+e.length+e.crossings*crossingCost+(dir&&dir!==e.dir?bendCost:0);
    if(score>=dist[next])continue;
    dist[next]=score;prev[next]=state;heap.push({state:next,cost:score});
   }
  }
  if(goal<0)return null;
  remaining.delete(Math.floor(goal/3));
  for(let s=goal;prev[s]>=0;s=prev[s]){
   const a=Math.floor(s/3),b=Math.floor(prev[s]/3);link(a,b);tree.add(a);tree.add(b);
  }
 }
 // Add the actual signed pin leads as tree edges; they are never search nodes.
 const routePoints=[...points];
 const pinIndex=new Map<number,number>();
 for(const [i,p] of ports.entries()){
  const id=routePoints.length;routePoints.push(p.pin);pinIndex.set(id,i);link(id,terminals[i]!);
 }
 const anchors=[...adj.keys()].filter(v=>pinIndex.has(v)||adj.get(v)!.size!==2);
 if(anchors.some(v=>!pinIndex.has(v)&&adj.get(v)!.size<3))return null;
 const anchorSet=new Set(anchors),used=new Set<string>(),paths:TreePath[]=[];
 const edgeKey=(a:number,b:number)=>a<b?a+':'+b:b+':'+a;
 let lengthUm=0,bends=0;
 for(const start of anchors)for(const first of adj.get(start)!){
  if(used.has(edgeKey(start,first)))continue;
  const route=[routePoints[start]];let a=start,b=first;
  while(true){
   used.add(edgeKey(a,b));route.push(routePoints[b]);lengthUm+=length(routePoints[a],routePoints[b]);
   if(anchorSet.has(b))break;
   const next=[...adj.get(b)!].find(v=>v!==a)!;a=b;b=next;
  }
  const compact:TreePoint[]=[route[0]];
  for(let i=1;i<route.length-1;i++){
   const p=route[i-1],q=route[i],r=route[i+1];
   if((p[0]===q[0]&&q[0]===r[0])||(p[1]===q[1]&&q[1]===r[1]))continue;
   compact.push(q);
  }
  compact.push(route.at(-1)!);bends+=compact.length-2;
  paths.push({points:compact,startPin:pinIndex.get(start)??null,endPin:pinIndex.get(b)??null});
 }
 return {paths,nodes:anchors.filter(v=>!pinIndex.has(v)).map(v=>routePoints[v]),lengthUm,bends};
 };
 const baseline=grow(false),candidate=grow(true);
 if(!baseline)return candidate;
 if(!candidate)return baseline;
 const score=(p:TreePlan)=>p.lengthUm+bendCost*p.bends+crossingCost*p.paths.reduce((n,path)=>
  n+path.points.slice(1).reduce((k,v,i)=>k+crossBoxes.filter(c=>overlaps(box(path.points[i],v),c.b)).length,0),0);
 // Greedy tree growth is not globally optimal. Keep the old solution if
 // the lead-aware candidate increases the number of bends or weighted cost.
 return candidate.bends<=baseline.bends&&score(candidate)<=score(baseline)?candidate:baseline;
}
