"""Offline, in-memory Chromium pointer smoke using exact #120 JS source.

No server/navigation: modules are inlined without changing their function bodies,
with only the export/import transport statements stripped. This isolates geometry
mouse behavior but IS NOT a React/Vite/Tauri end-to-end test.
"""
from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
SOURCE_DIR = HERE.parents[1] / 'editor/src/canvas'
PJS = SOURCE_DIR / 'precision.mjs'
SJS = SOURCE_DIR / 'scene-projection.mjs'


def run():
    html = (HERE/'browser-pointer-harness.html').read_text(encoding='utf-8')
    # Canvas is large enough that both X and pin are inside at 200% zoom.
    html = html.replace('width:820px;height:500px','width:1600px;height:1000px')
    html = html.replace('0 0 820 500','0 0 1600 1000')
    html = html.replace('top:600px','top:1150px')
    modules = []
    for path in (PJS,SJS):
        content = path.read_text(encoding='utf-8')
        content = re.sub(r'export \{[^}]*\};\s*$', '', content)
        modules.append(content)
    html = html.replace('<script type="module">', '<script>\n' + '\n'.join(modules))
    html = re.sub(r"^import \{[^\n]*?\} from '[^\n]*';\n", '', html, flags=re.MULTILINE)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1900,'height':1250},device_scale_factor=1)
        errors=[]
        page.on('pageerror',lambda err: errors.append(str(err)))
        page.set_content(html,wait_until='load')
        page.wait_for_function('window.qa?.ready === true')
        checks=0
        for scale in (.004,.008,.016):
            page.evaluate('(s)=>window.qa.setScale(s)',scale)
            c=page.evaluate('window.qa.toClient([50000,50000])')
            page.mouse.move(c['x'],c['y'])
            assert page.evaluate('window.qa.lastHover.kind')=='ambiguous-segment'
            page.mouse.click(c['x'],c['y'])
            hit=page.evaluate('window.qa.lastClick')
            assert hit['kind']=='ambiguous-segment' and len(hit['candidates'])==2,hit
            pin=page.evaluate('window.qa.toClient([2000,10000])')
            page.mouse.click(pin['x'],pin['y'])
            ph=page.evaluate('window.qa.lastClick')
            assert ph['kind']=='pin' and ph['pin']=={'component_id':'U1','physical_pin_number':'1'},ph
            page.evaluate('window.qa.setSnap(false)')
            assert page.evaluate('window.qa.snapped([1001,1002])')==[1001,1002]
            page.evaluate('window.qa.setGrid(false)')
            assert not page.evaluate('window.qa.gridVisible()')
            checks+=5
            print('PASS scale',scale,'CSSpx/um: hover X, click X, pin identity, snap/grid')
        assert not errors,errors
        image=HERE/'browser-pointer-offline.png'
        page.screenshot(path=str(image))
        print('PASS actual Chromium mouse events',checks,'assertions / browser',browser.version,'/ screenshot',image)
        browser.close()

if __name__=='__main__':run()