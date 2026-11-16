import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { visualTokens } from './tokens.ts';
const contrast=(a:string,b:string)=>{
  const l=(hex:string)=>{const rgb=hex.slice(1).match(/../g)!.map(x=>parseInt(x,16)/255).map(c=>c<=0.04045?c/12.92:((c+0.055)/1.055)**2.4);return 0.2126*rgb[0]+0.7152*rgb[1]+0.0722*rgb[2];};
  const [x,y]=[l(a),l(b)].sort((a,b)=>b-a);return (x+0.05)/(y+0.05);
};
test('normal + muted foreground pair AA in both themes',()=>{
  for(const p of Object.values(visualTokens)){assert.ok(contrast(p.ink,p.pane)>=4.5);assert.ok(contrast(p.muted,p.pane)>=4.5);}
});
test('symmetric semantic keys in both themes',()=>assert.deepEqual(Object.keys(visualTokens.dark),Object.keys(visualTokens.light)));
