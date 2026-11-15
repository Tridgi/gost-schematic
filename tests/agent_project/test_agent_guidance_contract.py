"""Agent instructions must reflect real shipped P1.1 and BLOCKED TL494 writes."""
import subprocess
import sys
from pathlib import Path

from gost_schematic.agent_project.agent_readiness import _OUTPUTS, _TL494_REFS
from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.agent_project.design_assistant import (
    TL494_BASELINE,
    TL494_FROZEN_SOURCE_SHA,
    TL494_REQUIRED_PARTS,
    tl494_profile,
)

ROOT = Path(__file__).resolve().parents[2]


def test_root_agent_and_skill_are_source_first_and_exist():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    skill = (ROOT / "skills/gost-schematic/SKILL.md").read_text(encoding="utf-8")
    assert skill.startswith("---\nname: gost-schematic\n")
    assert "AGENTS.md" in skill
    for content in (agents, skill):
        assert TL494_FROZEN_SOURCE_SHA in content
        for token in ("23", "15", "16", "62", "91", "37"):
            assert token in content
        assert "BLOCKED" in content
        assert "read-only" in content.lower() or "READ-ONLY" in content
        assert "schematic_catalog_select" in content
        assert "schematic_describe_project" in content
        assert "schematic_preflight_project" in content
        assert "schematic_preview_placement" in content
        assert "capacitor.polarized" in content
        assert "resistor.variable" in content
        assert "FEEDBACK" in content and "OUTPUT CTRL" in content
        assert "DA1.12" in content
        assert "3" in content and "2" in content and "1" in content
    assert "P1.1" in skill
    assert "C3" in agents and "six-part" in agents
    assert "NO" in agents and "main" in agents


def test_guidance_does_not_claim_synthetic_source_pass():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    skill = (ROOT / "skills/gost-schematic/SKILL.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs/ai-integration/agent-readiness-cli-v01.md").read_text(
        encoding="utf-8"
    )
    for content in (agents, skill, contract):
        assert "MCP" in content
        assert "Codex" in content
        assert "15" in content
        assert "DRAFT" in content
        assert "readiness" in content
        assert "CAS" in content
    for output in _OUTPUTS:
        assert output in contract
    assert "print_ready=false" in contract or "print_ready" in contract


def test_guidance_tl494_matrix_matches_current_source_catalog():
    profile = tl494_profile(CatalogResolver())
    assert profile["frozen_source_git_commit_sha"] == TL494_FROZEN_SOURCE_SHA
    assert len(_TL494_REFS) == TL494_BASELINE["component_count"] == 23
    assert TL494_BASELINE["net_count"] == 15
    assert len(TL494_REQUIRED_PARTS) == 13
    assert profile["tl494_device_catalog"] == "NOT_IN_INSTALLED_P11_CATALOG"
    ref_ids = {v["reference"]: v["required_part_id"] for v in profile["required_variants"]}
    assert ref_ids == TL494_REQUIRED_PARTS
    for ref, part in ref_ids.items():
        assert ref in (ROOT / "skills/gost-schematic/SKILL.md").read_text(encoding="utf-8")
        assert part in (ROOT / "AGENTS.md").read_text(encoding="utf-8")



def test_cycle13_quickstart_docs_use_installed_real_cli_and_safe_codex_commands():
    quickstart = (ROOT / "docs/ai-integration/cycle13-end-user-quickstart.md").read_text(
        encoding="utf-8"
    )
    codex = (ROOT / "docs/ai-integration/cycle13-codex-readonly-prompt.md").read_text(
        encoding="utf-8"
    )
    future = (ROOT / "docs/ai-integration/cycle13-future-transactions-safety.md").read_text(
        encoding="utf-8"
    )
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    skill = (ROOT / "skills/gost-schematic/SKILL.md").read_text(
        encoding="utf-8"
    )
    full_command = (
        "python -m examples.agent_tl494_cycle13_quickstart "
        "--out output/tl494-cycle13-user"
    )
    for doc in (quickstart, codex, readme, agents, skill):
        assert full_command in doc
        assert "BLOCKED" in doc
        assert "23" in doc and "15" in doc and "62" in doc
    assert "source_netlist_user_approval" in quickstart
    assert "USER_REVIEW_REQUIRED" in quickstart
    assert "refusal-tests.json" in quickstart
    assert "source-quickstart-report.json" in quickstart
    assert "codex mcp add gost-schematic-readonly -- python -m gost_schematic.mcp_server" in (
        quickstart
    )
    assert "codex mcp list" in codex
    assert "readOnlyHint=true" in future
    assert "atomic" in future.lower()
    assert "No" in future and "MCP" in future

    cmd = subprocess.run(
        [sys.executable, "-m", "examples.agent_tl494_cycle13_quickstart",
         "--help"],
        capture_output=True, text=True, check=True,
    )
    assert "--out" in cmd.stdout
    assert "write" in cmd.stdout.lower() or "read-only" in cmd.stdout.lower()
