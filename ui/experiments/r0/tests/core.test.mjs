import test from 'node:test';import assert from 'node:assert/strict';
import {demo,deep,LIBRARY,verifyProject,serialized,resolvePin,snap,appendWire,routePoints,moveSegment,reanchor,pointOnSegment,exportSvg,withPngDpi,removeWire} from '../core.mjs';
const pin=(id,number)=>({symbolId:id,number:String(number)});
test('synthetic demo has genuine 16 physical numeric demo pins, not source-verified',()=>{const p=demo();assert.equal(LIBRARY['ic.tl494.demo'].pins.length,16);assert.equal(p.provenance.kind,'synthetic-demo');assert.equal(p.sheets[0].symbols.length,3);assert.equal(p.sheets[0].nets.length,0);verifyProject(p);});
test('1 micrometre coordinate JSON roundtrip / deterministic serialization',()=>{const p=demo();p.sheets[0].symbols[0].x=85001;const encoded=serialized(p),parsed=JSON.parse(encoded);assert.equal(parsed.sheets[0].symbols[0].x,85001);assert.equal(encoded,serialized(parsed));});
test('snap off never changes integer position',()=>assert.equal(snap(123001,5000,false),123001));
test('orthogonal pin to pin and preserved net on save reopen',()=>{const p=demo(),s=p.sheets[0];const w=appendWire(s,pin('r1',2),pin('c1',1));assert.equal(s.nets.length,1);assert.equal(w.points.length,4);assert.deepEqual(w.points[0],resolvePin(s,w.start.pin));assert.deepEqual(w.points.at(-1),resolvePin(s,w.end.pin));verifyProject(JSON.parse(serialized(p)));});
test('middle segment move, undo by snapshot, invariants intact',()=>{const p=demo(),s=p.sheets[0],w=appendWire(s,pin('r1',2),pin('c1',1)),original=deep(w.points);moveSegment(w,1,3000);assert.equal(w.points[1].x,original[1].x+3000);assert.equal(w.points[2].x,original[2].x+3000);verifyProject(p);w.points=original;verifyProject(p);});
test('moving symbol reanchors physical PinRef and attached segment',()=>{const p=demo(),s=p.sheets[0],w=appendWire(s,pin('r1',2),pin('c1',1));s.symbols[0].x+=1000;reanchor(s,'r1');assert.deepEqual(w.points[0],resolvePin(s,w.start.pin));verifyProject(p);});
test('pure crossing has no electric junction',()=>{const a={x:0,y:5000},b={x:10000,y:5000},c={x:5000,y:0},d={x:5000,y:10000};assert.equal(pointOnSegment({x:5000,y:5000},a,b),true);assert.equal(pointOnSegment({x:5000,y:5000},c,d),true);const p=demo();assert.equal(p.sheets[0].junctions.length,0);});
test('different original named nets reject forbidden merge',()=>{const p=demo(),s=p.sheets[0];s.nets.push({id:'source-A',name:'S_A',members:[pin('r1',1)],source:'locked'},{id:'source-B',name:'S_B',members:[pin('c1',2)],source:'locked'});assert.throws(()=>appendWire(s,pin('r1',1),pin('c1',2)),/NET_MERGE_DENIED/);assert.equal(s.wires.length,0);});
test('falsified pin number rejected',()=>{const p=demo(),s=p.sheets[0];s.nets.push({id:'bad',name:'INVALID',members:[pin('da1',17)]});assert.throws(()=>verifyProject(p),/INVALID_NET_PIN/);});
test('wire endpoint drift rejected to 1 micrometre',()=>{const p=demo(),s=p.sheets[0];const w=appendWire(s,pin('r1',2),pin('c1',1));w.points[0].x++;assert.throws(()=>verifyProject(p),/PIN_DRIFT/);});
test('native SVG uses mm and pin labels but no UI selection/grid overlays',()=>{const p=demo(),s=p.sheets[0];appendWire(s,pin('r1',2),pin('c1',1));const svg=exportSvg(p,'sheet-1');assert.match(svg,/width="420mm" height="297mm"/);assert.match(svg,/data-net-id=/);assert.match(svg,/TL494/);assert.doesNotMatch(svg,/id="grid"|selection-outline|pin-target/);});
test('explicit graphics never create an electrical PinRef',()=>{const p=demo(),s=p.sheets[0];s.graphics.push({type:'line',a:{x:11001,y:10001},b:{x:14002,y:10001}});assert.equal(s.nets.length,0);assert.match(exportSvg(p,'sheet-1'),/data-non-electrical="true"/);});
test('unsupported schema version fails closed',()=>{const p=demo();p.version=2;assert.throws(()=>verifyProject(p),/UNSUPPORTED_PROJECT_FORMAT/);});
test('PNG pHYs 300 dpi roundtrip metadata',()=>{const base=Uint8Array.from(Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/mt8AAAAASUVORK5CYII=','base64'));const out=withPngDpi(base,300);assert.equal(Buffer.from(out.slice(37,41)).toString(),'pHYs');const d=new DataView(out.buffer);assert.equal(d.getUint32(41),11811);assert.equal(d.getUint32(45),11811);assert.equal(out[49],1);});

test('R/C exact draft source pins ±8mm match locked blob geometry',()=>{const p=demo(),s=p.sheets[0];assert.equal(resolvePin(s,pin('r1',1)).x,77000);assert.equal(resolvePin(s,pin('r1',2)).x,93000);assert.equal(resolvePin(s,pin('c1',1)).x,222000);assert.match(exportSvg(p,'sheet-1'),/M -8 0 H -0.75/);});
test('user-authored net can extend to a third valid physical PinRef only',()=>{const p=demo(),s=p.sheets[0];const a=appendWire(s,pin('r1',2),pin('c1',1));const b=appendWire(s,pin('r1',2),pin('da1',1));assert.equal(s.nets.length,1);assert.equal(s.nets[0].members.length,3);assert.equal(a.netId,b.netId);verifyProject(p);});
test('known-source net membership fails closed against new external pin',()=>{const p=demo(),s=p.sheets[0];s.nets.push({id:'locked',name:'SRC',members:[pin('r1',2)],source:'locked'});assert.throws(()=>appendWire(s,pin('r1',2),pin('c1',1)),/NET_MERGE_DENIED/);assert.equal(s.nets[0].members.length,1);});

test('PNG dpi patch replaces existing pHYs without duplicate chunks',()=>{const base=Uint8Array.from(Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/mt8AAAAASUVORK5CYII=','base64'));const once=withPngDpi(base,96);const twice=withPngDpi(once,300);assert.equal(twice.length,once.length);assert.equal(Buffer.from(twice).toString('latin1').split('pHYs').length-1,1);assert.equal(new DataView(twice.buffer).getUint32(41),11811);});

test('junction must reference at least two authored same-Net wires, not pixels alone',()=>{const p=demo(),s=p.sheets[0];const a=appendWire(s,pin('r1',2),pin('c1',1)),b=appendWire(s,pin('r1',2),pin('da1',1)),point=resolvePin(s,pin('r1',2));const j={id:'J1',netId:a.netId,x:point.x,y:point.y,connectedWireIds:[a.id,b.id]};s.junctions.push(j);verifyProject(p);const bad=deep(j);bad.id='J2';bad.connectedWireIds=['nonexistent',b.id];s.junctions.push(bad);assert.throws(()=>verifyProject(p),/INVALID_JUNCTION/);});


test('wrong-Net membership cannot be smuggled through a wire endpoint',()=>{
  const p=demo(),s=p.sheets[0];
  const w=appendWire(s,pin('r1',2),pin('c1',1));
  s.nets.push({id:'other',name:'OTHER',source:'locked',members:[pin('da1',1)]});
  w.end.pin=pin('da1',1);
  w.points.at(-1).x=resolvePin(s,w.end.pin).x;
  w.points.at(-1).y=resolvePin(s,w.end.pin).y;
  assert.throws(()=>verifyProject(p),/PIN_NET_MISMATCH/);
});

test('injected duplicate physical contact between source Nets is rejected',()=>{
  const p=demo(),s=p.sheets[0];
  s.nets.push({id:'a',name:'A',source:'locked',members:[pin('r1',1)]});
  s.nets.push({id:'b',name:'B',source:'locked',members:[pin('r1',1)]});
  assert.throws(()=>verifyProject(p),/DUPLICATE_NET_MEMBERSHIP/);
});

test('invalid waypoint rolls back prospective Net.member and Wire as one operation',()=>{
  const p=demo(),s=p.sheets[0];appendWire(s,pin('r1',2),pin('c1',1));
  const baseline=serialized(p);
  assert.throws(()=>appendWire(s,pin('c1',1),pin('da1',1),[{x:1.5,y:1000}]),/INVALID_WAYPOINTS/);
  assert.equal(serialized(p),baseline);
});

test('coincident distinct physical pins cannot create a zero-length electrical conductor',()=>{
  const p=demo(),s=p.sheets[0];
  s.symbols[1].x=101000;s.symbols[1].y=90000; // C1.1 and R1.2 overlap geometrically
  const before=serialized(p);
  assert.throws(()=>appendWire(s,pin('r1',2),pin('c1',1)),/ZERO_LENGTH_WIRE/);
  assert.equal(serialized(p),before);
});

test('deleting wire cleans orphaned explicit junctions atomically',()=>{
  const p=demo(),s=p.sheets[0];
  const a=appendWire(s,pin('r1',2),pin('c1',1));
  const b=appendWire(s,pin('r1',2),pin('da1',1));
  const at=resolvePin(s,pin('r1',2));
  s.junctions.push({id:'junction',netId:a.netId,x:at.x,y:at.y,connectedWireIds:[a.id,b.id]});
  verifyProject(p);
  removeWire(s,a.id);
  assert.equal(s.wires.length,1);
  assert.equal(s.junctions.length,0);
  verifyProject(p);
});

test('empty sheet collection, duplicate sheet ids and fractional coordinates fail closed',()=>{
  const p=demo();p.sheets=[];
  assert.throws(()=>verifyProject(p),/INVALID_SHEET_COUNT/);
  const q=demo();q.sheets.push(deep(q.sheets[0]));
  assert.throws(()=>verifyProject(q),/INVALID_SHEET/);
  const r=demo();r.sheets[0].symbols[0].x+=0.5;
  assert.throws(()=>verifyProject(r),/INVALID_SYMBOL/);
});

test('a malformed move is rejected on serialization rather than saved',()=>{
  const p=demo(),s=p.sheets[0],w=appendWire(s,pin('r1',2),pin('c1',1));
  w.points[1].x+=1;w.points[1].y+=1;
  assert.throws(()=>serialized(p),/NON_ORTHOGONAL/);
});
