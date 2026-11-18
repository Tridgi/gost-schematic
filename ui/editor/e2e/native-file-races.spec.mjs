import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';

const fixture=JSON.parse(readFileSync(
  new URL('../public/fixtures/tl494-source-e695-v2.gscad.json',import.meta.url),'utf8'));

test('grid and snap are persisted project changes, not silent disposable preferences',async({page})=>{
  await page.goto('/');
  await expect(page.getByTestId('gscad-signed-svg-canvas')).toBeVisible();
  const dirty=page.getByTestId('project-toolbar').getByText('Не сохранено',{exact:true});
  await expect(dirty).toHaveCount(0);
  await page.getByRole('button',{name:'Показать сетку'}).click();
  await expect(dirty).toBeVisible();
  await page.getByRole('button',{name:'Привязка к сетке'}).click();
  await expect(dirty).toBeVisible();
  const downloaded=page.waitForEvent('download');
  await page.getByTestId('save-project').click();
  const saved=JSON.parse(readFileSync(await (await downloaded).path(),'utf8'));
  expect(saved.project.settings.grid_visible).toBe(false);
  expect(saved.project.settings.snap_enabled).toBe(true);
  await expect(dirty).toHaveCount(0);
  await page.reload();
  await expect(page.getByTestId('gscad-signed-svg-canvas')).toBeVisible();
  await page.getByTestId('project-file-input').setInputFiles({
    name:'settings.gscad.json',mimeType:'application/json',
    buffer:Buffer.from(JSON.stringify(saved),'utf8')
  });
  await expect(page.getByRole('button',{name:'Показать сетку'}))
    .toHaveAttribute('aria-pressed','false');
  await expect(page.getByRole('button',{name:'Привязка к сетке'}))
    .toHaveAttribute('aria-pressed','true');
});

test('native Save As completion never clears edits made while OS save dialog is pending',async({page})=>{
  await page.addInitScript(()=>{
    window.__gscadMock={pendingSave:null};
    window.__TAURI__={core:{invoke:(command,args)=>{
      if(command==='native_save_as_project')return new Promise(resolve=>{
        window.__gscadMock.pendingSave={args,resolve};
      });
      if(command==='native_close_project')return Promise.resolve();
      throw Error('UNEXPECTED_NATIVE_COMMAND: '+command);
    }},window:{getCurrentWindow:()=>({onCloseRequested:async()=>()=>{}})}};
  });
  await page.goto('/');
  await expect(page.getByTestId('gscad-signed-svg-canvas')).toBeVisible();
  await page.getByTestId('save-project').click();
  await page.waitForFunction(()=>!!window.__gscadMock.pendingSave);
  await page.getByRole('button',{name:'Показать сетку'}).click();
  await expect(page.getByTestId('project-toolbar').getByText('Не сохранено',{exact:true})).toBeVisible();
  await page.evaluate(()=>{
    const pending=window.__gscadMock.pendingSave;
    pending.resolve({
      handle:'opaque-native-1',generation:0,
      project_sha256:'a'.repeat(64),filename:'saved-before-edit.gscad.json',
      document:pending.args.document
    });
  });
  await expect(page.getByTestId('project-toolbar').getByText('Не сохранено',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:/ERC/}).click();
  await expect(page.getByText(/SAVE_COMPLETED_BUT_DOCUMENT_CHANGED/)).toBeVisible();
});

test('native Open completion never discards edits created after picker invocation',async({page})=>{
  await page.addInitScript(()=>{
    window.__gscadMock={pendingOpen:null,closedHandles:[]};
    window.__TAURI__={core:{invoke:(command,args)=>{
      if(command==='native_open_project')return new Promise(resolve=>{
        window.__gscadMock.pendingOpen={resolve};
      });
      if(command==='native_close_project'){
        window.__gscadMock.closedHandles.push(args.handle);
        return Promise.resolve();
      }
      throw Error('UNEXPECTED_NATIVE_COMMAND: '+command);
    }},window:{getCurrentWindow:()=>({onCloseRequested:async()=>()=>{}})}};
  });
  await page.goto('/');
  await expect(page.getByTestId('gscad-signed-svg-canvas')).toBeVisible();
  const originalTitle=fixture.project.title;
  const loaded=structuredClone(fixture);
  loaded.project.title='Should not replace dirty canvas';
  await page.getByRole('button',{name:'Файл'}).click();
  await page.getByText('Открыть…',{exact:true}).click();
  await page.waitForFunction(()=>!!window.__gscadMock.pendingOpen);
  await page.getByRole('button',{name:'Показать сетку'}).click();
  await expect(page.getByTestId('project-toolbar').getByText('Не сохранено',{exact:true})).toBeVisible();
  await page.evaluate(document=>{
    window.__gscadMock.pendingOpen.resolve({
      handle:'aborted-open',generation:0,project_sha256:'b'.repeat(64),
      filename:'other.gscad.json',document
    });
  },loaded);
  await expect(page.getByRole('button',{name:'Показать сетку'}))
    .toHaveAttribute('aria-pressed','false');
  await expect(page.getByTestId('project-toolbar').getByText('Не сохранено',{exact:true})).toBeVisible();
  await expect(page.locator('.gscad-project-label')).toContainText(originalTitle);
  await expect.poll(()=>page.evaluate(()=>
    window.__gscadMock.closedHandles.includes('aborted-open'))).toBe(true);
});


test('Tauri native window-close blocks discarded edits unless the user confirms',async({page})=>{
  await page.addInitScript(()=>{
    // React StrictMode registers, removes and registers the listener again.
    // Real Tauri unsubscribe removes only its own callback, not all listeners.
    window.__gscadMock={onClose:null,listeners:new Set()};
    window.__TAURI__={
      core:{invoke:async()=>{throw Error('NO_COMMAND_EXPECTED');}},
      window:{getCurrentWindow:()=>({
        onCloseRequested:async listener=>{
          const m=window.__gscadMock;
          m.listeners.add(listener);m.onClose=listener;
          return ()=>{
            m.listeners.delete(listener);
            m.onClose=[...m.listeners].at(-1)??null;
          };
        }
      })}
    };
  });
  await page.goto('/');
  await expect(page.getByTestId('gscad-signed-svg-canvas')).toBeVisible();
  await page.waitForFunction(()=>!!window.__gscadMock.onClose);
  const fire=()=>page.evaluate(()=>{
    let blocked=false;
    window.__gscadMock.onClose({preventDefault(){blocked=true;}});
    return blocked;
  });
  expect(await fire()).toBe(false,'clean application window may close');
  await page.getByRole('button',{name:'Показать сетку'}).click();
  await page.evaluate(()=>{window.confirm=()=>false;});
  expect(await fire()).toBe(true,'unsaved changes require close cancellation');
  await page.evaluate(()=>{window.confirm=()=>true;});
  expect(await fire()).toBe(false,'explicit user confirmation permits close');
});

test('native Save As does not overlap another save and releases superseded Rust handles',async({page})=>{
  await page.addInitScript(()=>{
    window.__gscadMock={saves:[],closes:[]};
    window.__TAURI__={
      core:{invoke:(command,args)=>{
        if(command==='native_save_as_project')return new Promise(resolve=>{
          window.__gscadMock.saves.push({resolve,args});
        });
        if(command==='native_close_project'){
          window.__gscadMock.closes.push(args.handle);
          return Promise.resolve();
        }
        throw Error('UNEXPECTED_NATIVE_COMMAND: '+command);
      }},
      window:{getCurrentWindow:()=>({onCloseRequested:async()=>()=>{}})}
    };
  });
  await page.goto('/');
  await expect(page.getByTestId('gscad-signed-svg-canvas')).toBeVisible();
  await page.getByTestId('save-project').click();
  await page.waitForFunction(()=>window.__gscadMock.saves.length===1);
  await page.getByTestId('save-project').click();
  await page.getByRole('button',{name:/ERC/}).click();
  await expect(page.getByText(/NATIVE_SAVE_BUSY/)).toBeVisible();
  expect(await page.evaluate(()=>window.__gscadMock.saves.length)).toBe(1);
  await page.evaluate(()=>{
    const saved=window.__gscadMock.saves[0];
    saved.resolve({
      handle:'native-first',generation:0,filename:'first.gscad.json',
      project_sha256:'a'.repeat(64),document:saved.args.document
    });
  });
  await expect(page.getByText(/NATIVE_SAVED/)).toBeVisible();
  await page.getByRole('button',{name:'Файл'}).click();
  await page.getByTestId('save-project-as').click();
  await page.waitForFunction(()=>window.__gscadMock.saves.length===2);
  await page.evaluate(()=>{
    const saved=window.__gscadMock.saves[1];
    saved.resolve({
      handle:'native-second',generation:0,filename:'second.gscad.json',
      project_sha256:'b'.repeat(64),document:saved.args.document
    });
  });
  await expect.poll(()=>page.evaluate(()=>window.__gscadMock.closes))
    .toEqual(['native-first']);
});
