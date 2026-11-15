// Node.js 22.16.0 proof: canonical SHA256 on JSON schema's integer-only project subset.
// Compare output to Python contract.digest(). No network/dependencies.
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
const path = process.argv[2];
const record=JSON.parse(readFileSync(path,'utf8'));
function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value !== null && typeof value==='object') {
    return `{${Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical(value[k])).join(',')}}`;
  }
  if (typeof value === 'number' && !Number.isSafeInteger(value))throw new Error('NON_INTEGER');
  return JSON.stringify(value);
}
const projectCanonical=canonical(record.project);
const hash=createHash('sha256').update('GSCAD_PROJECT_V2\0','utf8').update(projectCanonical,'utf8').digest('hex');
process.stdout.write(hash+'\n');
