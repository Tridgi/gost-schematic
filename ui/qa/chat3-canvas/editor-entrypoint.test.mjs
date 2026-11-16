/** CHAT3 R2: exact entrypoint/lockfile checks, not a compiled React smoke.
 * Designed to fail fast when a newly committed integration shell lacks App.tsx,
 * app.css or a reproducible npm ci lock. MASTER #125 owns all three paths.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync,readFileSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
const editor=resolve(dirname(fileURLToPath(import.meta.url)),'../../editor');
const present=relative=>existsSync(resolve(editor,relative));
const main=readFileSync(resolve(editor,'src/main.tsx'),'utf8');

test('Vite preview has HTML root and real TypeScript entrypoint',()=>{
  assert.ok(present('index.html'));
  assert.ok(present('src/main.tsx'));
  assert.match(readFileSync(resolve(editor,'index.html'),'utf8'),/id=["']root["']/);
});
test('React entrypoint relative ./App resolves to real authored module',()=>{
  assert.match(main,/from ['"]\.\/App['"]/);
  assert.ok(['src/App.tsx','src/App.ts','src/App.jsx','src/App.js','src/App/index.tsx'].some(present),
    'ENTRYPOINT_MISSING_APP: ui/editor/src/main.tsx imports ./App, but no module exists');
});
test('React entrypoint stylesheet ./app.css exists at authored path',()=>{
  assert.match(main,/import ['"]\.\/app\.css['"]/);
  assert.ok(present('src/app.css'),'ENTRYPOINT_MISSING_STYLESHEET');
});
test('R2 reproducible npm ci has an editor lockfile',()=>{
  assert.ok(present('package-lock.json'),'R2_NPM_CI_BLOCKED_MISSING_PACKAGE_LOCK');
});
