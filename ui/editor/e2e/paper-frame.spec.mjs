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
