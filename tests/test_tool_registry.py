import json
from pathlib import Path

from cua_lark.tool_registry import build_tool_registry, write_mcp_manifest


def test_tool_registry_contains_phase8_tools() -> None:
    registry = build_tool_registry()

    assert sorted(registry.tools) == [
        "feishu.im.latest_message",
        "feishuworld.eval.run_suite",
        "feishuworld.trace.export",
        "system.clipboard.set",
    ]
    assert registry.tools["feishuworld.trace.export"].side_effects.startswith("Writes dataset")
    assert registry.tools["feishu.im.latest_message"].side_effects.startswith("Read-only")


def test_write_mcp_manifest_is_stable(tmp_path: Path) -> None:
    manifest_path = write_mcp_manifest(build_tool_registry(), tmp_path / "mcp_manifest.json")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "mcp-ready.v1"
    assert [tool["name"] for tool in manifest["tools"]] == [
        "feishuworld.eval.run_suite",
        "feishuworld.trace.export",
        "feishu.im.latest_message",
        "system.clipboard.set",
    ]
    assert manifest["tools"][1]["implementation"] == "cua_lark.trace.exporter.export_trace_datasets"
