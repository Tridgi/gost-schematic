"""Real Chromium pointer events against the exact #120 JS modules.

Run: python ui/qa/chat3-canvas/browser-pointer-smoke.py
Needs: playwright package and installed Chromium; no npm or CDN.
This is a geometry adapter smoke, NOT the released React/Vite/Tauri app.
"""
from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[4]
HTML = '/ui/qa/chat3-canvas/browser-pointer-harness.html'

def run() -> None:
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=str(ROOT)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True, executable_path='/usr/bin/chromium', args=['--no-sandbox'])
            page = browser.new_page(viewport={'width': 1100, 'height': 740}, device_scale_factor=1)
            failures = []
            page.on('pageerror', lambda err: failures.append(str(err)))
            page.goto(f'http://127.0.0.1:{server.server_port}{HTML}', wait_until='networkidle')
            page.wait_for_function('window.qa?.ready === true')
            for scale in (.004, .008, .016):
                page.evaluate('(scale) => window.qa.setScale(scale)', scale)
                crossing = page.evaluate('window.qa.toClient([50000,50000])')
                page.mouse.move(crossing['x'],crossing['y'])
                assert page.evaluate('window.qa.lastHover.kind') == 'ambiguous-segment'
                page.mouse.click(crossing['x'],crossing['y'])
                hit = page.evaluate('window.qa.lastClick')
                assert hit['kind'] == 'ambiguous-segment' and len(hit['candidates']) == 2, hit
                pin = page.evaluate('window.qa.toClient([2000,10000])')
                page.mouse.click(pin['x'],pin['y'])
                hit = page.evaluate('window.qa.lastClick')
                assert hit['kind'] == 'pin', hit
                assert hit['pin'] == {'component_id':'U1','physical_pin_number':'1'}, hit
                page.evaluate('window.qa.setSnap(false)')
                assert page.evaluate('window.qa.snapped([1001,1002])') == [1001,1002]
                page.evaluate('window.qa.setGrid(false)')
                assert page.evaluate('window.qa.gridVisible()') is False
                # A disabled grid doesn't change pin identity.
                page.mouse.click(pin['x'],pin['y'])
                assert page.evaluate('window.qa.lastClick.pin.physical_pin_number') == '1'
                print(f'PASS actual Chromium pointer+hover (scale={scale} px/um, pin/X, snap/grid independent)')
            assert not failures, failures
            png = Path(__file__).resolve().parent / 'browser-pointer-smoke.png'
            page.screenshot(path=str(png))
            print('PASS Chromium', browser.version, 'screenshot',png)
            browser.close()
    finally:
        server.shutdown()
        server.server_close()

if __name__ == '__main__':
    run()