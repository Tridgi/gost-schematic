// Dependency-free Node -> Python subprocess smoke. No shell or network.
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
const root = dirname(fileURLToPath(import.meta.url));
const py = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
const child = spawn(py, ['-u', join(root, 'worker.py')], { shell: false, stdio: ['pipe', 'pipe', 'pipe'] });
let errors = '';
child.stderr.setEncoding('utf8');
child.stderr.on('data', s => errors += s);
const pending = new Map();
createInterface({ input: child.stdout }).on('line', line => {
  try {
    const reply = JSON.parse(line);
    const entry = pending.get(reply.id);
    if (entry) { pending.delete(reply.id); entry.resolve(reply); }
    else { errors += 'Unexpected response ' + reply.id + '\n'; }
  } catch (error) { errors += 'Invalid response: ' + error + '\n'; }
});
const send = (id, op, args = {}) => new Promise((resolve, reject) => {
  pending.set(id, {resolve, reject});
  child.stdin.write(JSON.stringify({v:1, id, op, args}) + '\n');
});
const timeout = setTimeout(() => {
  child.kill();
  for (const entry of pending.values()) entry.reject(new Error('sidecar timeout'));
  pending.clear();
}, 7000);
try {
  const [hello, um, deny, symbol] = await Promise.all([
    send('hello1', 'hello'),
    send('um1', 'unit_roundtrip', {x_um:'9223372036854775807', y_um:'-9223372036854775808'}),
    send('bad1', 'shell', {cmd:'echo exploit'}),
    send('symbol1', 'check_symbol', {symbol:'resistors/fixed.json'}),
  ]);
  assert.equal(hello.result.protocol, 1);
  assert.equal(hello.result.project_write, false);
  assert.equal(um.result.y_um, '-9223372036854775808');
  assert.equal(deny.error.code, 'UNKNOWN_OPERATION');
  assert.equal(symbol.ok || symbol.error.code === 'ENGINE_UNAVAILABLE', true);
  if (process.env.GSCAD_REQUIRE_ENGINE === '1') {
    assert.equal(symbol.ok, true, 'CI requires real installed Python engine');
  }
  const sourceFile = join(root, '..', '..', 'fixtures', 'tl494-source-e695-v2.gscad.json');
  if (existsSync(sourceFile)) {
    const document = JSON.parse(readFileSync(sourceFile, 'utf8'));
    const snapshot = await send('v2snapshot', 'source_snapshot', {document});
    assert.equal(snapshot.ok, true, JSON.stringify(snapshot));
    assert.equal(snapshot.result.inventory.components, 23);
    assert.equal(snapshot.result.inventory.nets, 15);
    assert.equal(snapshot.result.inventory.memberships, 62);
    assert.equal(snapshot.result.inventory.non_electrical_b, 2);
    assert.equal(snapshot.result.inventory.wires, 0);
    assert.equal(snapshot.result.declared_routes.unrouted, 15);
    const net = document.project.nets.find(n => n.members.length > 1);
    assert.ok(net);
    const check = await send('v2net', 'verify_net', {document, net_id: net.id});
    assert.equal(check.ok, true, JSON.stringify(check));
    assert.equal(check.result.reachability_complete, false);
    assert.equal(check.result.export_approved, false);
    console.log('PASS canonical ProjectV2 E695 source and read-only Net reachability');
  } else {
    if (process.env.GSCAD_REQUIRE_V2 === '1') {
      throw new Error('CI requires canonical ProjectV2 fixture and model');
    }
    console.log('SKIP canonical ProjectV2 fixture is not installed in this worktree');
  }
  assert.equal(errors, '');
  console.log('PASS Node -> Python NDJSON: correlation, int64, shell denial; engine:', symbol.ok ? 'PASS' : 'ENGINE_UNAVAILABLE');
} finally {
  clearTimeout(timeout);
  child.stdin.end();
}
