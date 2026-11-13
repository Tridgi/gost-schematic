"""Summarize real Codex CLI JSONL without printing MCP image base64 or secrets."""
import argparse
import base64
import hashlib
import json
from pathlib import Path


def summarize(path: Path) -> dict[str, object]:
    events = []
    images = []
    messages = []
    errors = []
    turns = 0
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            if not line.strip():
                continue
            event = json.loads(line)
            item = event.get("item") or {}
            if event.get("type") == "turn.completed":
                turns += 1
            if event.get("type") == "item.completed" and item.get("type") == "agent_message":
                messages.append(item.get("text", ""))
            if item.get("type") != "mcp_tool_call" or event.get("type") != "item.completed":
                continue
            info = {
                "tool": item.get("tool"),
                "status": item.get("status"),
                "args": item.get("arguments"),
                "has_error": (
                    item.get("error") is not None
                    or item.get("status") != "completed"
                    or bool((item.get("result") or {}).get("isError"))
                ),
            }
            if info["has_error"]:
                errors.append(info)
            blocks = (item.get("result") or {}).get("content") or []
            content_types = []
            for block in blocks:
                kind = block.get("type")
                content_types.append(kind)
                if kind == "image":
                    payload = base64.b64decode(block.get("data") or "")
                    images.append({
                        "tool": item.get("tool"),
                        "mime_type": block.get("mimeType"),
                        "valid_png_magic": payload[:8] == b"\x89PNG\r\n\x1a\n",
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "byte_count": len(payload),
                    })
                if kind == "text":
                    try:
                        data = json.loads(block.get("text", ""))
                        if isinstance(data, dict) and "project_revision" in data:
                            info["project_revision"] = data["project_revision"]
                            if data.get("selected_component"):
                                info["component"] = data["selected_component"]
                    except (ValueError, TypeError):
                        pass
            info["content_types"] = content_types
            events.append(info)
    return {
        "source": str(path),
        "completed_turns": turns,
        "mcp_calls": events,
        "images": images,
        "errors": errors,
        "agent_messages": messages,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("jsonl", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    document = summarize(args.jsonl)
    payload = json.dumps(document, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
        print(f"Scrubbed report: {args.output}")
    else:
        print(payload)


if __name__ == "__main__":
    main()
