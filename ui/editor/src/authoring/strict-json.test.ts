import test from 'node:test';
import assert from 'node:assert/strict';
import {parseProjectJsonStrict} from './strict-json.ts';

test('strict parser preserves clean ProjectV2 data without mutation',()=>{
 const text='{"format":"gscad-project","format_version":2,"project":{"id":"p"},"workspace":{}}';
 assert.deepEqual(parseProjectJsonStrict(text),JSON.parse(text));
});
test('duplicate top-level and nested keys fail closed including Unicode escaped aliases',()=>{
 for(const bad of [
   '{"format":"gscad-project","format":"unexpected"}',
   '{"project":{"nets":[{"members":[],"members":[]}]}}',
   '{"project":{"source_sha":"a","source_\\u0073ha":"b"}}',
   '{"component":{"id":"R1","id":"R2"}}'
 ]){
   assert.throws(()=>parseProjectJsonStrict(bad),/DUPLICATE_JSON_KEY/);
 }
});
test('corrupt, trailing, incomplete, unsafe-depth, and nonstandard numbers are rejected',()=>{
 for(const bad of ['{','{"a":1,}','{"a":NaN}','{}{}','{"a":"\\uQQQQ"}',
   '['.repeat(98)+'0'+']'.repeat(98)]){
   assert.throws(()=>parseProjectJsonStrict(bad));
 }
});
