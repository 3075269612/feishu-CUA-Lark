from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    side_effects: str
    implementation: str


@dataclass(frozen=True)
class ToolRegistry:
    tools: dict[str, ToolSpec]

    def as_manifest(self) -> dict[str, Any]:
        return {
            "schema_version": "mcp-ready.v1",
            "description": "Local CUA-Lark tool registry prepared for future MCP wrapping.",
            "tools": [asdict(tool) for tool in self.tools.values()],
        }


def build_tool_registry() -> ToolRegistry:
    tools = {
        "feishuworld.eval.run_suite": ToolSpec(
            name="feishuworld.eval.run_suite",
            description="Run a FeishuWorld eval suite through the existing eval CLI path.",
            input_schema={
                "type": "object",
                "required": ["suite_path", "profile", "runs_dir"],
                "properties": {
                    "suite_path": {"type": "string"},
                    "profile": {"type": "string", "enum": ["mock", "real-smoke-dry-run", "real-smoke"]},
                    "runs_dir": {"type": "string"},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "exit_code": {"type": "integer"},
                    "summary_json": {"type": "string"},
                    "summary_md": {"type": "string"},
                },
            },
            side_effects="May execute UI actions depending on profile; real-smoke sends messages and creates docs.",
            implementation="cua_lark.eval.runner.run_eval_suite",
        ),
        "feishuworld.trace.export": ToolSpec(
            name="feishuworld.trace.export",
            description="Export trace-derived datasets for Phase 8 data preparation.",
            input_schema={
                "type": "object",
                "required": ["runs_dir", "output_dir"],
                "properties": {
                    "runs_dir": {"type": "string"},
                    "output_dir": {"type": "string"},
                    "statuses": {"type": "array", "items": {"type": "string"}},
                    "include_products": {"type": "array", "items": {"type": "string"}},
                    "max_runs": {"type": "integer"},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "exported_runs": {"type": "integer"},
                    "grounding_examples": {"type": "integer"},
                    "fewshot_examples": {"type": "integer"},
                    "generated_files": {"type": "object"},
                },
            },
            side_effects="Writes dataset JSONL, summary files, and an MCP-ready manifest.",
            implementation="cua_lark.trace.exporter.export_trace_datasets",
        ),
        "feishu.im.latest_message": ToolSpec(
            name="feishu.im.latest_message",
            description="Read the latest message from an allowed Feishu test chat for oracle verification.",
            input_schema={
                "type": "object",
                "required": ["chat_name"],
                "properties": {
                    "chat_name": {"type": "string"},
                    "text_contains": {"type": "string"},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "chat_id": {"type": "string"},
                    "matched_count": {"type": "integer"},
                    "recent_texts": {"type": "array", "items": {"type": "string"}},
                },
            },
            side_effects="Read-only Feishu OpenAPI oracle call.",
            implementation="cua_lark.feishu.im_api.ImApi.latest_message_contains",
        ),
        "system.clipboard.set": ToolSpec(
            name="system.clipboard.set",
            description="Set local clipboard text before a GUI paste action.",
            input_schema={
                "type": "object",
                "required": ["text"],
                "properties": {"text": {"type": "string"}},
            },
            output_schema={
                "type": "object",
                "properties": {"status": {"type": "string"}, "reason": {"type": "string"}},
            },
            side_effects="Mutates the local clipboard.",
            implementation="cua_lark.actions.clipboard.set_clipboard_text",
        ),
    }
    return ToolRegistry(tools=tools)


def write_mcp_manifest(registry: ToolRegistry, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry.as_manifest(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path
