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
