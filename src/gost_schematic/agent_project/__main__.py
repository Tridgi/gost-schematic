"""Trusted local P1.1 demo CLI; not an MCP edit endpoint."""
import argparse
import json
from pathlib import Path

from .catalog import ProjectError
from .service import ProjectService
from .trusted_import import import_six_part, new_ids


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path,
                        help="Trusted host-selected storage root; not an MCP user path")
    commands = parser.add_subparsers(dest="command", required=True)
    first = commands.add_parser("import-six-part")
    first.add_argument("--project-id")
    first.add_argument("--idempotency-key")
    opened = commands.add_parser("open")
    opened.add_argument("project_id")
    opened.add_argument("--revision")
    render = commands.add_parser("render")
    render.add_argument("project_id")
    render.add_argument("revision")
    render.add_argument("--component")
    args = parser.parse_args()
    try:
        if args.command == "import-six-part":
            project_id, request_id = new_ids()
            snapshot = import_six_part(args.workspace,
                project_id=args.project_id or project_id,
                idempotency_key=args.idempotency_key or request_id)
            result = {"project_id": snapshot.head.project_id,
                      "revision": snapshot.head.revision,
                      "generation": snapshot.head.generation}
        else:
            service = ProjectService.for_workspace(args.workspace)
            if args.command == "open":
                snapshot = service.open_project(args.project_id, args.revision)
                result = service.validate_project(args.project_id,
                                                   snapshot.project.revision)
            else:
                view = service.render_project(args.project_id, args.revision,
                                              reference=args.component)
                output = (service.repository.root / "artifacts" / args.project_id /
                          args.revision)
                output.mkdir(parents=True, exist_ok=True)
                prefix = "C3" if args.component == "C3" else "overview"
                (output / (prefix + ".svg")).write_text(view.svg, encoding="utf-8")
                (output / (prefix + ".png")).write_bytes(view.png)
                result = {**view.metadata, "artifact_directory": str(output)}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    except ProjectError as exc:
        parser.exit(2, f"{exc.code}: {exc}\n")


if __name__ == "__main__":
    main()
