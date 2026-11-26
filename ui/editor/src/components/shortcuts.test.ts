import {test} from 'node:test';
import {strict as assert} from 'node:assert';
import {resolveShellShortcut as k} from './shortcuts.ts';
test('V W H T select tools outside text fields',()=>{
 for(const [key,expected] of [['v','select'],['W','wire'],['h','pan'],['T','text']] as const)
   assert.equal(k({key}),expected);
});
test('editing blocks bare shortcuts, but Ctrl+K command palette still opens',()=>{
 assert.equal(k({key:'w'},{editable:true}),null);
 assert.equal(k({key:'k',ctrlKey:true},{editable:true}),'palette');
 assert.equal(k({key:'e',ctrlKey:true},{editable:true}),'export');
 assert.equal(k({key:'z',ctrlKey:true},{editable:true}),null);
 assert.equal(k({key:'s',ctrlKey:true},{editable:true}),null);
});
test('Ctrl+S/Z/Shift+Z/Y and Meta shortcuts in canvas focus',()=>{
 assert.equal(k({key:'s',ctrlKey:true}),'save');
 assert.equal(k({key:'z',ctrlKey:true}),'undo');
 assert.equal(k({key:'z',ctrlKey:true,shiftKey:true}),'redo');
 assert.equal(k({key:'y',ctrlKey:true}),'redo');
 assert.equal(k({key:'k',metaKey:true}),'palette');
});
test('never steal IME, active dialog, alt chords, repeat or consumed events',()=>{
 assert.equal(k({key:'w',isComposing:true}),null);
 assert.equal(k({key:'w',repeat:true}),null);
 assert.equal(k({key:'w',defaultPrevented:true}),null);
 assert.equal(k({key:'w',altKey:true}),null);
 assert.equal(k({key:'w'},{dialogOpen:true}),null);
 assert.equal(k({key:'k',ctrlKey:true},{dialogOpen:true}),null);
 assert.equal(k({key:'W',shiftKey:true}),null);
});

test('CAD clipboard shortcuts never steal native text or dialog clipboard actions',()=>{
 for(const [key,action] of [['c','copy'],['v','paste']] as const){
  assert.equal(k({key,ctrlKey:true}),action);
  assert.equal(k({key,metaKey:true}),action);
  assert.equal(k({key,ctrlKey:true},{editable:true}),null);
  assert.equal(k({key,ctrlKey:true},{dialogOpen:true}),null);
  assert.equal(k({key,ctrlKey:true,shiftKey:true}),null);
 }
});

 test('Visio and Office aliases never intercept text editing',()=>{
 for(const [key,action] of [['1','select'],['3','wire'],['a','selectAll'],['d','duplicate'],['f','findCatalog'],['n','newProject'],['o','openProject']] as const){
 assert.equal(k({key,ctrlKey:true}),action);assert.equal(k({key,ctrlKey:true},{editable:true}),null);
 }
 assert.equal(k({key:'s',ctrlKey:true,shiftKey:true}),'saveAs');
 assert.equal(k({key:'F2'}),'properties');assert.equal(k({key:'F2'},{editable:true}),null);
 });
