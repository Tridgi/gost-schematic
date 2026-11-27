/** Exact cardinal curve contract; sampled chords are only for hit testing.
 * Rendering/export must use the analytic circle or SVG A command. */
export function curveGeometry(kind,pts){
 const invalid=()=>{throw Error('INVALID_CURVE')};
 const safe=p=>Array.isArray(p)&&p.length===2&&p.every(n=>Number.isSafeInteger(n)&&Math.abs(n)<=1e9);
 if(!Array.isArray(pts)||!pts.every(safe))invalid();
 if(kind==='circle'){
  if(pts.length!==2)invalid();
  const [center,rim]=pts,dx=rim[0]-center[0],dy=rim[1]-center[1];
  if((dx===0)===(dy===0))invalid();
  const radius=Math.abs(dx)+Math.abs(dy);
  if(center.some(n=>Math.abs(n)+radius>1e9))invalid();
  return {center,radius,sweep:0,bounds:[[center[0]-radius,center[1]-radius],[center[0]+radius,center[1]+radius]]};
 }
 if(kind!=='semicircle'||pts.length!==3)invalid();
 const [start,apex,end]=pts,center=[(start[0]+end[0])/2,(start[1]+end[1])/2];
 const dx=start[0]-center[0],dy=start[1]-center[1],ux=apex[0]-center[0],uy=apex[1]-center[1];
 const radius=Math.abs(dx)+Math.abs(dy);
 if(!safe(center)||(dx===0)===(dy===0)||dx*ux+dy*uy!==0||Math.abs(ux)+Math.abs(uy)!==radius||
  center.some(n=>Math.abs(n)+radius>1e9))invalid();
 return {center,radius,sweep:dx*uy-dy*ux>0?1:0,bounds:[start,apex,end]};
}
export function curveChords(kind,pts){
 const {center,radius,sweep}=curveGeometry(kind,pts);
 const count=kind==='circle'?96:48;
 const start=kind==='circle'?pts[1]:pts[0];
 const angle=Math.atan2(start[1]-center[1],start[0]-center[0]);
 const span=kind==='circle'?2*Math.PI:(sweep?1:-1)*Math.PI;
 const samples=Array.from({length:count+1},(_,i)=>[
  Math.round(center[0]+radius*Math.cos(angle+i/count*span)),
  Math.round(center[1]+radius*Math.sin(angle+i/count*span))
 ]);
 samples[0]=start;samples[count]=kind==='circle'?start:pts[2];
 if(kind==='semicircle')samples[count/2]=pts[1];
 return samples.slice(1).flatMap((p,i)=>p[0]===samples[i][0]&&p[1]===samples[i][1]?[]:[{from_um:samples[i],to_um:p}]);
}
