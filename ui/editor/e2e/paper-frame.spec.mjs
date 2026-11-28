import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';

/** R10 paper guides use the authoritative ProjectV2 frame.
 * Neither the visual sheet nor its print margins may become electrical ink.
 */
test('R10: synthetic A3 canvas marks real paper and print margins without adding Nets',async({page})=>{
  await page.goto('/');
  await expect(page.getByTestId('gscad-signed-svg-canvas')).toBeVisible();
  await page.getByRole('button',{name:'Файл'}).click();
  await page.getByTestId('new-project').click();
  await expect(page.getByText(/R3 AUTHORING/)).toBeVisible();

  const guide=page.locator('g.cad-paper-guide');
  await expect(guide).toHaveAttribute('data-electrical','false');
  const paper=page.getByTestId('gscad-paper-outline');
  const margins=page.getByTestId('gscad-print-margin');
  await expect(paper).toBeVisible();
  await expect(margins).toBeVisible();
  const width=Number(await paper.getAttribute('width'));
  const height=Number(await paper.getAttribute('height'));
  const mWidth=Number(await margins.getAttribute('width'));
  const mHeight=Number(await margins.getAttribute('height'));
  expect(width).toBeGreaterThan(0);
  expect(height).toBeGreaterThan(0);
  expect(width/height).toBeCloseTo(420/297,6);
  expect(mWidth/width).toBeCloseTo(400/420,6);
  expect(mHeight/height).toBeCloseTo(277/297,6);
  await expect(page.getByTestId('gscad-paper-label')).toContainText('A3 landscape');

  // A canvas-only guide never creates an authored graphic, PinRef or Net.
  const download=page.waitForEvent('download');
  await page.getByTestId('save-project').click();
  const doc=JSON.parse(readFileSync(await (await download).path(),'utf8'));
  expect(doc.project.sheets[0].frame.size_um).toEqual([420000,297000]);
  expect(doc.project.sheets[0].graphics).toEqual([]);
  expect(doc.project.components).toEqual([]);
  expect(doc.project.nets).toEqual([]);
});


test('R10: A4/A2 paper actions fit viewport, persist exact µm and support Undo/Redo',async({page})=>{
  await page.goto('/');
  await page.getByRole('button',{name:'Файл'}).click();
  await page.getByTestId('new-project').click();
  const svg=page.getByTestId('gscad-signed-svg-canvas');
  const outline=page.getByTestId('gscad-paper-outline');
  const withinCanvas=async()=>{
    const a=await svg.boundingBox(),b=await outline.boundingBox();
    expect(a).toBeTruthy();expect(b).toBeTruthy();
    expect(b.x).toBeGreaterThanOrEqual(a.x+20);
    expect(b.y).toBeGreaterThanOrEqual(a.y+20);
    expect(b.x+b.width).toBeLessThanOrEqual(a.x+a.width-20);
    expect(b.y+b.height).toBeLessThanOrEqual(a.y+a.height-20);
  };
  const changePaper=async size=>{
    await page.getByRole('button',{name:'Файл'}).click();
    await page.getByTestId('paper-format-'+size).click();
    await expect(page.getByTestId('gscad-paper-label')).toContainText(size+' landscape');
    await withinCanvas();
  };
  await withinCanvas();
  await changePaper('A4');
  await expect(outline).toHaveAttribute('width',/^[0-9.]+$/);
  expect(Number(await outline.getAttribute('width'))/Number(await outline.getAttribute('height')))
    .toBeCloseTo(297/210,6);
  await changePaper('A2');
  expect(Number(await outline.getAttribute('width'))/Number(await outline.getAttribute('height')))
    .toBeCloseTo(594/420,6);
  await page.getByRole('button',{name:'Отменить'}).click();
  await expect(page.getByTestId('gscad-paper-label')).toContainText('A4 landscape');
  await page.getByRole('button',{name:'Повторить'}).click();
  await expect(page.getByTestId('gscad-paper-label')).toContainText('A2 landscape');
  const download=page.waitForEvent('download');
  await page.getByTestId('save-project').click();
  const saved=JSON.parse(readFileSync(await (await download).path(),'utf8'));
  expect(saved.project.sheets[0].frame).toEqual({paper:'A2 landscape',size_um:[594000,420000],margin_um:10000});
  expect(saved.project.nets).toEqual([]);
  expect(saved.project.sheets[0].graphics).toEqual([]);
});


test('R10: shrinking A3 with positioned component warns without silently moving signed ink',async({page})=>{
  await page.goto('/');
  await page.getByRole('button',{name:'Файл'}).click();
  await page.getByTestId('new-project').click();
  const outline=page.getByTestId('gscad-paper-outline');
  const before=await outline.boundingBox();
  expect(before).toBeTruthy();
  await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
  await page.mouse.click(before.x+before.width*.88,before.y+before.height*.45);
  await expect(page.getByTestId('symbol-R1')).toHaveCount(1);
  await expect(page.getByTestId('gscad-paper-warning')).toHaveCount(0);
  const download=page.waitForEvent('download');
  await page.getByTestId('save-project').click();
  const a3=JSON.parse(readFileSync(await (await download).path(),'utf8'));
  const origin=a3.project.sheets[0].instances[0].origin_um;
  expect(origin[0]).toBeGreaterThan(297000);
  await page.getByRole('button',{name:'Файл'}).click();
  await page.getByTestId('paper-format-A4').click();
  await expect(page.getByTestId('gscad-paper-warning')).toContainText('1 УГО');
  await page.getByRole('button',{name:'Отменить'}).click();
  await expect(page.getByTestId('gscad-paper-warning')).toHaveCount(0);
  await page.getByRole('button',{name:'Повторить'}).click();
  await expect(page.getByTestId('gscad-paper-warning')).toContainText('1 УГО');
  await page.getByRole('button',{name:'Файл'}).click();
  await page.getByTestId('paper-format-A2').click();
  await expect(page.getByTestId('gscad-paper-warning')).toHaveCount(0);
  const newer=page.waitForEvent('download');
  await page.getByTestId('save-project').click();
  const a2=JSON.parse(readFileSync(await (await newer).path(),'utf8'));
  expect(a2.project.sheets[0].instances[0].origin_um).toEqual(origin);
  expect(a2.project.nets).toEqual([]);
});


test('R10: explicit Fit resets wheel/pan camera without editing physical model',async({page})=>{
 await page.goto('/');
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 const paper=page.getByTestId('gscad-paper-outline');
 const svg=page.getByTestId('gscad-signed-svg-canvas');
 const start=await paper.boundingBox();
 expect(start).toBeTruthy();
 const canvas=await svg.boundingBox();
 await page.mouse.move(canvas.x+canvas.width/2,canvas.y+canvas.height/2);
 for(let i=0;i<6;i++)await page.mouse.wheel(0,-600);
 await expect.poll(async()=>Number(await paper.getAttribute('width')))
   .toBeGreaterThan(start.width*1.5);
 await page.getByRole('button',{name:'Масштаб'}).click();
 await page.getByTestId('fit-page').click();
 await expect.poll(async()=>Math.abs(Number(await paper.getAttribute('width'))-start.width)/start.width)
   .toBeLessThan(0.02);
 const after=await paper.boundingBox();
 expect(after.x).toBeGreaterThanOrEqual(canvas.x+20);
 expect(after.x+after.width).toBeLessThanOrEqual(canvas.x+canvas.width-20);
 const download=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const doc=JSON.parse(readFileSync(await (await download).path(),'utf8'));
 expect(doc.project.nets).toEqual([]);
 expect(doc.project.sheets[0].frame.size_um).toEqual([420000,297000]);
});


test('R10: A4/A2 physical SVG excludes guides, A4 PNG300 carries exact pHYs and pixels',async({page})=>{
 await page.goto('/');
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('paper-format-A4').click();
 const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
 await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
 await page.mouse.click(paper.x+paper.width*.4,paper.y+paper.height*.4);
 for(const [size,w,h] of [['A4',297,210],['A2',594,420]]){
   if(size==='A2'){
     await page.getByRole('button',{name:'Файл'}).click();
     await page.getByTestId('paper-format-A2').click();
   }
   await page.getByRole('button',{name:'Экспорт',exact:true}).click();
   const pending=page.waitForEvent('download');
   await page.getByRole('button',{name:'Экспортировать'}).click();
   const data=readFileSync(await (await pending).path(),'utf8');
   expect(data).toContain('width="'+w+'mm" height="'+h+'mm"');
   expect(data).toContain('data-layer="symbols"');
   expect(data).not.toMatch(/cad-paper-guide|gscad-paper-outline|gscad-print-margin|cad-grid-um/);
 }
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('paper-format-A4').click();
 await page.getByRole('button',{name:'Экспорт',exact:true}).click();
 await page.getByText('PNG 300 DPI',{exact:true}).click();
 const pending=page.waitForEvent('download');
 await page.getByRole('button',{name:'Экспортировать'}).click();
 const png=readFileSync(await (await pending).path());
 expect(png.readUInt32BE(16)).toBe(Math.round(297/25.4*300));
 expect(png.readUInt32BE(20)).toBe(Math.round(210/25.4*300));
 const phys=png.indexOf(Buffer.from('pHYs'));
 expect(phys).toBeGreaterThan(0);
 expect(png.readUInt32BE(phys+4)).toBe(11811);
 expect(png.readUInt32BE(phys+8)).toBe(11811);
});


test('R55 shrinking A3 warns about rotated printable text without moving or deleting it',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Файл',exact:true}).click();
 await page.getByTestId('new-project').click();
 const canvas=page.getByTestId('gscad-signed-svg-canvas');
 await expect(canvas).toHaveAttribute('data-camera-ready','true');
 const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
 await canvas.focus();await canvas.press('t');
 await page.mouse.click(paper.x+paper.width*.5,paper.y+paper.height*.5);
 await page.getByTestId('sheet-text-input').fill('MMMMMM');
 await page.getByTestId('add-sheet-text').click();
 const annotation=canvas.locator('text[data-testid^="sheet-text-"]');
 await expect(annotation).toHaveCount(1);await annotation.dblclick();
 const dialog=page.getByRole('dialog',{name:'Свойства надписи'});
 await dialog.getByTestId('sheet-text-x').fill('150');
 await dialog.getByTestId('sheet-text-y').fill('180');
 await dialog.getByText('5',{exact:true}).click();
 await dialog.getByText('90',{exact:true}).click();
 await dialog.getByTestId('add-sheet-text').click();await expect(dialog).toBeHidden();
 const save=async()=>{const d=page.waitForEvent('download');await page.getByTestId('save-project').click();return JSON.parse(readFileSync(await (await d).path(),'utf8'));};
 const before=await save();
 await expect(page.getByTestId('gscad-paper-warning')).toHaveCount(0);
 await page.getByRole('button',{name:'Файл',exact:true}).click();
 await page.getByTestId('paper-format-A4').click();
 await expect(page.getByTestId('gscad-paper-warning')).toContainText('1 надписей');
 const after=await save(),expected=structuredClone(before.project);
 expected.sheets[0].frame={...expected.sheets[0].frame,paper:'A4 landscape',size_um:[297000,210000]};
 expect(after.project).toEqual(expected);
 await page.getByRole('button',{name:'Отменить'}).click();
 await expect(page.getByTestId('gscad-paper-warning')).toHaveCount(0);
 expect((await save()).project).toEqual(before.project);
 await page.getByRole('button',{name:'Повторить'}).click();
 await expect(page.getByTestId('gscad-paper-warning')).toContainText('1 надписей');
 expect((await save()).project).toEqual(after.project);
});
