import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { parseMillimetres, formatMillimetres, MAX_POINT_UM } from './inspector-units.ts';
test('exact 1µm, signed, locale-comma and boundary roundtrip',()=>{
  for (const um of [0,1,-1,1234,-1234567,MAX_POINT_UM,-MAX_POINT_UM])
    assert.deepEqual(parseMillimetres(formatMillimetres(um)),{ok:true,um});
  assert.deepEqual(parseMillimetres(' 2,005 '),{ok:true,um:2005});
});
test('reject rounding and unsupported inputs without optimistic mutation',()=>{
  for(const s of ['1.0001','1,0001'])assert.deepEqual(parseMillimetres(s),{ok:false,code:'PRECISION'});
  for(const s of ['NaN','Infinity','1e4','1,2.3','1 000','--3','1.','abc'])
    assert.deepEqual(parseMillimetres(s),{ok:false,code:'INVALID_FORMAT'});
  assert.deepEqual(parseMillimetres(''),{ok:false,code:'EMPTY'});
  assert.deepEqual(parseMillimetres('1000000.001'),{ok:false,code:'OUT_OF_RANGE'});
  assert.deepEqual(parseMillimetres('99999999999999999999'),{ok:false,code:'OUT_OF_RANGE'});
  assert.throws(()=>formatMillimetres(1.5),RangeError);
});
