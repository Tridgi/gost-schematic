import test from 'node:test';
import assert from 'node:assert/strict';
import {assessRelease,compareStableVersions,checkLatestRelease,RELEASE_API} from './release-check.ts';
const stable=(tag_name:string)=>({tag_name,draft:false,prerelease:false});
test('stable releases use numeric ordering and never recommend downgrades',()=>{
  assert.equal(compareStableVersions('v0.10.0','0.9.9'),1);
  assert.deepEqual(assessRelease('0.2.0',stable('v0.1.9')),{kind:'current',version:'v0.1.9'});
  assert.equal(assessRelease('0.1.0',stable('v0.1.0')).kind,'current');
  assert.equal(assessRelease('0.1.0',stable('v0.2.0')).kind,'available');
});
test('malformed, prerelease and draft metadata fails closed',()=>{
  for(const payload of [null,{},stable('v0.2.0-rc.1'),stable('v01.2.3'),stable('v9999999999999999999.2.3'),{...stable('v0.2.0'),draft:true},{...stable('v0.2.0'),prerelease:true}])
    assert.throws(()=>assessRelease('0.1.0',payload));
});
test('fixed endpoint and no credentials, no redirect, no public release',async()=>{
  const signal=new AbortController().signal;
  const request:typeof fetch=async(url,options)=>{
    assert.equal(url,RELEASE_API);assert.equal(options?.credentials,'omit');
    assert.equal(options?.redirect,'error');assert.equal(options?.signal,signal);
    return new Response(null,{status:404});
  };
  assert.deepEqual(await checkLatestRelease('0.1.0',signal,request),{kind:'none'});
  await assert.rejects(checkLatestRelease('0.1.0',signal,async()=>new Response(null,{status:403})));
});
