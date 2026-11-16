"""CHAT1 #117: RED Chromium UX regression for inspector-focused Ctrl+Z in R0.

Requires Playwright Python + local Chromium (as existing R0 browser_smoke.py).
Runs the *real* source at ui/experiments/r0, not a mock. R0 is experimental;
failure is not automatically an R2 production release blocker.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "ui" / "experiments" / "r0" / "tests"))
import browser_smoke as r0


def main() -> None:
    browser_path = shutil.which("chromium") or shutil.which("chromium-browser")
    if browser_path is None:
        raise RuntimeError("BLOCKED: Chromium binary unavailable")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=browser_path,
            headless=True,
            args=["--no-sandbox", "--disable-gpu"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 900}, accept_downloads=True)
        page.evaluate(
            """() => {
              const storage=new Map();
              Object.defineProperty(window,'localStorage',{configurable:true,value:{
                getItem:k=>storage.get(k)??null,
                setItem:(k,v)=>storage.set(k,String(v)),
                removeItem:k=>storage.delete(k)
              }});
              window.confirm=()=>false;
            }"""
        )
        page.set_content(r0.html(), wait_until="load", timeout=15000)
        page.wait_for_timeout(150)
        page.locator('.hit-symbol[data-symbol="r1"]').first.click()
        field = page.locator("#field-value")
        field.fill("R0-committed")
        field.press("Tab")  # fires change -> one committed editor transaction

        def current_saved_value() -> str:
            with tempfile.TemporaryDirectory() as tmp:
                dest = Path(tmp) / "project.json"
                with page.expect_download(timeout=10000) as dl:
                    # DOM click does not steal input focus or trigger blur.
                    page.evaluate("document.getElementById('save-btn').click()")
                dl.value.save_as(dest)
                data = json.loads(dest.read_text(encoding="utf-8"))
                return next(
                    obj["value"]
                    for obj in data["sheets"][0]["symbols"]
                    if obj["id"] == "r1"
                )

        committed = current_saved_value()
        assert committed == "R0-committed"
        field = page.locator("#field-value")
        field.focus()
        page.keyboard.type("-editing")  # uncommitted text edit
        assert page.evaluate("document.activeElement.id") == "field-value"
        page.keyboard.press("Control+z")

        # Ctrl+Z is owned by focused input, not the CAD graph.
        # At the reviewed R0 app.mjs, global undo runs before `if(editing)return`:
        # this deliberately fails until #125 fixes the focus guard.
        after = current_saved_value()
        assert after == committed, (
            f"CAD-UX-FOCUS-01: input Ctrl+Z undid project transaction; "
            f"expected model value {committed!r}, actual {after!r}"
        )
        browser.close()


if __name__ == "__main__":
    main()
