"""R0 offline Chromium proof: inline module assets under an inert about:blank document.

The available CI sandbox blocks ALL navigation with ERR_BLOCKED_BY_ADMINISTRATOR;
this E2E verifies real browser interactions but not a served localhost/Vite app.
"""
from pathlib import Path
import base64
import json
import tempfile
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def html():
    text = (ROOT/'index.html').read_text()
    core64 = base64.b64encode((ROOT/'core.mjs').read_bytes()).decode()
    app = (ROOT/'app.mjs').read_text().replace("from './core.mjs'",f"from 'data:text/javascript;base64,{core64}'")
    text = text.replace('<link rel="stylesheet" href="style.css">', '<style>'+(ROOT/'style.css').read_text()+'</style>')
    text = text.replace('<script type="module" src="app.mjs"></script>', '<script type="module">'+app+'</script>')
    return text


def mouse_click_pin(page, symbol, number):
    loc = page.locator(f'circle[data-symbol="{symbol}"][data-pin="{number}"]')
    box = loc.bounding_box()
    assert box, f'missing visible physical pin {symbol}.{number}'
    x, y = box['x'] + box['width']/2, box['y'] + box['height']/2
    page.mouse.click(x,y)


def smoke():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-gpu'])
        page = browser.new_page(viewport={'width':1600,'height':900},accept_downloads=True)
        page.evaluate("""() => {const db=new Map();Object.defineProperty(window,'localStorage',{
            configurable:true,value:{getItem:k=>db.get(k)??null,setItem:(k,v)=>db.set(k,String(v)),
            removeItem:k=>db.delete(k)}});window.confirm=()=>false;}""")
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(html(),wait_until='load',timeout=15000)
        page.wait_for_timeout(150)
        assert page.locator('.symbol-art').count()==3
        color=page.locator('.symbol-art').first.evaluate('e=>getComputedStyle(e).color')
        assert color == 'rgb(32, 41, 53)',f'white-on-white symbols: {color}'
        page.locator('[data-tool="wire"]').first.click()
        mouse_click_pin(page,'r1','2')
        assert 'Начало провода' in page.locator('#status-msg').inner_text()
        mouse_click_pin(page,'c1','1')
        status=page.locator('#status-msg').inner_text()
        assert 'двум физическим PinRef' in status
        assert page.locator('.draw-wire').count()==1
        page.locator('#undo').click()
        assert page.locator('.draw-wire').count()==0, 'Undo must remove entire wire'
        page.locator('#redo').click()
        assert page.locator('.draw-wire').count()==1, 'Redo must restore same wire'

        # Save after actual pin-to-pin pointer action; use browser download bytes.
        with tempfile.TemporaryDirectory() as temporary:
            saved=Path(temporary)/'saved.gscad.json'
            with page.expect_download() as capture:page.locator('#save-btn').click()
            capture.value.save_as(saved)
            initial=json.loads(saved.read_text())
            wire=initial['sheets'][0]['wires'][0]
            assert wire['start']['pin']=={'symbolId':'r1','number':'2'}
            assert wire['end']['pin']=={'symbolId':'c1','number':'1'}
            original_points=wire['points']

            # Independent grid/snap controls are UI-only; neither mutates engineering data.
            page.locator('#grid-visible').uncheck()
            page.locator('#grid-snap').uncheck()
            page.locator('#theme-btn').click()
            assert page.locator('body').get_attribute('data-theme')=='light'
            page.locator('[data-tool="select"]').first.click()
            wirepath=page.locator('#canvas .hitwire[data-seg="1"]').first
            rect=wirepath.bounding_box()
            assert rect
            px=rect['x']+rect['width']/2;py=rect['y']+rect['height']/2
            scale=page.locator('#canvas').evaluate('e=>e.getScreenCTM().a')
            page.mouse.move(px,py)
            page.mouse.down()
            page.mouse.move(px+3*scale,py,steps=6)
            page.mouse.up()
            with page.expect_download() as capture:page.locator('#save-btn').click()
            capture.value.save_as(saved)
            moved=json.loads(saved.read_text())
            new_points=moved['sheets'][0]['wires'][0]['points']
            assert new_points!=original_points, f'Wire segment edit missed: {new_points}'
            delta=new_points[1]['x']-original_points[1]['x']
            assert 2900<=delta<=3100, f'Expected ~3mm movement, got {delta}um'
            assert new_points[0]==original_points[0] and new_points[-1]==original_points[-1]

            # Undo and redo complete geometry transaction, preserving PinRefs.
            page.locator('#undo').click()
            with page.expect_download() as capture:page.locator('#save-btn').click()
            capture.value.save_as(saved)
            reverted=json.loads(saved.read_text())
            assert reverted['sheets'][0]['wires'][0]['points']==original_points
            page.locator('#redo').click()
            with page.expect_download() as capture:page.locator('#save-btn').click()
            capture.value.save_as(saved)
            redone=json.loads(saved.read_text())
            assert redone['sheets'][0]['wires'][0]['points']==new_points

            with page.expect_download() as capture:page.locator('#svg-btn').click()
            svg_file=Path(temporary)/'drawing.svg';capture.value.save_as(svg_file)
            xml=svg_file.read_text()
            assert 'width="420mm"' in xml and 'data-wire-id' in xml and 'gridlines' not in xml
            assert 'data-net-id' in xml and 'data-pin=' not in xml

            # Browser canvas -> PNG tagged pHYs from the same canonical SVG output.
            with page.expect_download(timeout=15000) as capture:page.locator('#png-btn').click()
            png_file=Path(temporary)/'drawing.png';capture.value.save_as(png_file)
            with Image.open(png_file) as im:
                assert im.size==(4961,3508), f'Unexpected A3 PNG dims: {im.size}'
                assert abs(im.info['dpi'][0]-300)<0.01
            # Open exact saved project; electrical graph and geometry retained.
            page.locator('#open-file').set_input_files(saved)
            assert page.locator('.draw-wire').count()==1
            assert 'Загружен проект' in page.locator('#status-msg').inner_text()
        assert not errors, f'Browser errors: {errors}'
        page.screenshot(path='/mnt/data/r0-inline-e2e-final.png',full_page=True)
        print('E2E PASS: actual pin click -> wire -> undo/redo -> segment +3mm -> save/open -> clean SVG -> PNG 300DPI -> theme/grid/snap')
        browser.close()

if __name__ == '__main__':smoke()
