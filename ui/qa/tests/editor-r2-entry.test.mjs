import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

/**
 * RED acceptance gate for #125's Vite entrypoint. Dedicated strict command:
 * npm run test:r2-entry:strict (from ui/qa). A TS shell skeleton is not R2.
 */
test('CAD-UX-R2-06 — Vite entrypoint imports exist and npm ci lockfile is committed', () => {
  const root=fileURLToPath(new URL('../../editor/',import.meta.url));
  const main=readFileSync(join(root,'src/main.tsx'),'utf8');
  assert.match(main,/from ['"]\.\/App['"]/);
  assert.match(main,/import ['"]\.\/app\.css['"]/);
  for (const file of ['src/App.tsx','src/app.css','package-lock.json']) {
    assert(existsSync(join(root,file)), `BLOCKED: missing ${file}`);
  }
  const pkg=JSON.parse(readFileSync(join(root,'package.json'),'utf8'));
  const lock=JSON.parse(readFileSync(join(root,'package-lock.json'),'utf8'));
  assert.equal(lock.lockfileVersion>=2,true);
  assert.equal(lock.packages[''].name,pkg.name);
  assert.equal(lock.packages[''].version,pkg.version);
});
