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
type Edge={to:number;length:number;dir:1|2};
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
export function planOrthogonalTree(ports:TreePort[],obstacles:TreeBox[],frame:TreeBox):TreePlan|null{
 if(ports.length<3||ports.length>32||obstacles.length>640)return null;
 const inside=(p:TreePoint)=>p[0]>=frame.minX&&p[0]<=frame.maxX&&p[1]>=frame.minY&&p[1]<=frame.maxY;
 const stubs=ports.map(p=>box(p.pin,p.tip));
 if(ports.some(p=>!inside(p.tip)||!inside(p.pin)||eq(p.pin,p.tip)||(p.pin[0]!==p.tip[0]&&p.pin[1]!==p.tip[1])))return null;
 if(stubs.some((b,i)=>stubs.slice(i+1).some(c=>overlaps(b,c))))return null;
 let comparisons=0;
 const clear=(a:TreePoint,b:TreePoint)=>{
  const segment=box(a,b);
  for(const o of obstacles){if(++comparisons>3000000)throw Error('TREE_SEARCH_LIMIT');if(overlaps(segment,o))return false}
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
 for(const b of [...obstacles,...stubs]){
  xs.add(Math.floor(b.minX)-1);xs.add(Math.ceil(b.maxX)+1);
  ys.add(Math.floor(b.minY)-1);ys.add(Math.ceil(b.maxY)+1);
 }
 const X=[...xs].filter(x=>x>=frame.minX&&x<=frame.maxX).sort((a,b)=>a-b);
 const Y=[...ys].filter(y=>y>=frame.minY&&y<=frame.maxY).sort((a,b)=>a-b);
 if(X.length>96||Y.length>96||X.length*Y.length>6500)throw Error('TREE_GRID_LIMIT');
 const points:TreePoint[]=[],indices=new Map<string,number>(),edges:Edge[][]=[];
 const node=(p:TreePoint)=>indices.get(key(p));
 for(const y of Y)for(const x of X){
  const p:TreePoint=[x,y];if(!clear(p,p))continue;
  indices.set(key(p),points.length);points.push(p);edges.push([]);
 }
 const join=(a:TreePoint,b:TreePoint,dir:1|2)=>{
  const i=node(a),j=node(b);if(i===undefined||j===undefined||!clear(a,b))return;
  const len=length(a,b);edges[i].push({to:j,length:len,dir});edges[j].push({to:i,length:len,dir});
 };
 for(const y of Y)for(let x=1;x<X.length;x++)join([X[x-1],y],[X[x],y],1);
 for(const x of X)for(let y=1;y<Y.length;y++)join([x,Y[y-1]],[x,Y[y]],2);
 const terminals=ports.map(p=>node(p.tip));
 if(terminals.some(v=>v===undefined))return null;
 const remaining=new Set(terminals as number[]),root=terminals[0]!;
 const tree=new Set<number>([root]),adj=new Map<number,Set<number>>();
 remaining.delete(root);
 const link=(a:number,b:number)=>{const add=(x:number,y:number)=>{const s=adj.get(x)??new Set<number>();s.add(y);adj.set(x,s)};add(a,b);add(b,a)};
 while(remaining.size){
  const dist=new Float64Array(points.length*3).fill(Infinity),prev=new Int32Array(points.length*3).fill(-1),heap=new Heap();
  for(const v of tree){dist[v*3]=0;heap.push({state:v*3,cost:0})}
  let goal=-1;
  while(heap.size){
   const {state,cost}=heap.pop();if(cost!==dist[state])continue;
   const v=Math.floor(state/3),dir=state%3;
   if(remaining.has(v)){goal=state;break}
   for(const e of edges[v]){
    if(tree.has(e.to))continue;
    const next=e.to*3+e.dir,score=cost+e.length+(dir&&dir!==e.dir?5000:0);
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
 const pinIndex=new Map<number,number>();
 for(const [i,p] of ports.entries()){
  const id=points.length;points.push(p.pin);pinIndex.set(id,i);link(id,terminals[i]!);
 }
 const anchors=[...adj.keys()].filter(v=>pinIndex.has(v)||adj.get(v)!.size!==2);
 if(anchors.some(v=>!pinIndex.has(v)&&adj.get(v)!.size<3))return null;
 const anchorSet=new Set(anchors),used=new Set<string>(),paths:TreePath[]=[];
 const edgeKey=(a:number,b:number)=>a<b?a+':'+b:b+':'+a;
 let lengthUm=0,bends=0;
 for(const start of anchors)for(const first of adj.get(start)!){
  if(used.has(edgeKey(start,first)))continue;
  const route=[points[start]];let a=start,b=first;
  while(true){
   used.add(edgeKey(a,b));route.push(points[b]);lengthUm+=length(points[a],points[b]);
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
 return {paths,nodes:anchors.filter(v=>!pinIndex.has(v)).map(v=>points[v]),lengthUm,bends};
}
