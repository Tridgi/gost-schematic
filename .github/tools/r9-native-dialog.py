"""CI-only Windows IFileDialog operator. Uses real UI Automation, never a file-picker mock."""
import argparse
import os
import sys
import time
from pathlib import Path

from pywinauto import Desktop

parser = argparse.ArgumentParser()
parser.add_argument("--pid", type=int, required=True)
parser.add_argument("--mode", choices=["save", "open", "cancel"], required=True)
parser.add_argument("--path", required=True)
args = parser.parse_args()

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise RuntimeError("CI_ONLY_NATIVE_DIALOG_AUTOMATION")
runner = os.environ.get("RUNNER_TEMP", "")
if not runner or not Path(args.path).resolve(strict=False).is_relative_to(Path(runner).resolve()):
    raise RuntimeError("DIALOG_PATH_OUTSIDE_RUNNER_TEMP")
if args.pid <= 0:
    raise RuntimeError("INVALID_PID")

def log(message):
    print(message, flush=True)

last = None
desktop = Desktop(backend="uia")
for attempt in range(100):
    for window in desktop.windows():
        try:
            info = window.element_info
            if info.process_id != args.pid:
                continue
            if info.class_name != "#32770":
                continue
            edits = window.descendants(control_type="Edit")
            if not edits:
                continue
            # Windows IFileDialog uses AutomationId 1001 for the File name edit.
            filename = next((e for e in edits if str(e.element_info.automation_id) == "1001"), None)
            if filename is None:
                filename = next((e for e in edits if "file" in (e.element_info.name or "").lower()), None)
            if filename is None:
                last = "NO_FILENAME_EDIT:" + ",".join(str(e.element_info.automation_id) for e in edits[:8])
                continue
            log("R9_REAL_DIALOG_FOUND mode=" + args.mode +
                " class=" + info.class_name + " title=" + repr(info.name))
            if args.mode != "cancel":
                filename.set_edit_text(args.path)
            buttons = window.descendants(control_type="Button")
            button_id = "2" if args.mode == "cancel" else "1"
            action = next((b for b in buttons if str(b.element_info.automation_id) == button_id), None)
            if action is None:
                names = {"save": ("save", "сохранить"), "open": ("open", "открыть"),
                         "cancel": ("cancel", "отмена")}[args.mode]
                action = next((b for b in buttons if (b.element_info.name or "").lower().strip() in names), None)
            if action is None:
                last = "DIALOG_ACTION_BUTTON_NOT_FOUND:" + ",".join(
                    str(b.element_info.automation_id) + ":" + str(b.element_info.name)
                    for b in buttons[:12])
                continue
            action.invoke()
            log("R9_REAL_DIALOG_ACTION_SENT mode=" + args.mode)
            time.sleep(0.5)
            if window.is_visible():
                log("R9_REAL_DIALOG_STILL_VISIBLE_AFTER_ACTION mode=" + args.mode)
            # Returning from invoke is not enough: the caller verifies disk persistence.
            sys.exit(0)
        except Exception as exc:  # noqa: BLE001 - Windows UIA/COM exceptions vary by version
            last = type(exc).__name__ + ":" + str(exc)[:250]
    time.sleep(0.25)
raise RuntimeError("R9_REAL_NATIVE_DIALOG_NOT_CONTROLLED " + str(last))
