# Datasets

This directory documents trace-derived datasets for CUA-Lark.

Generated datasets are written under `datasets/generated/` and are ignored by Git because they can contain local run paths and references to real screenshots.

## Phase 8 Export

```bash
python -m cua_lark.main export-traces runs --out datasets/generated/feishuworld_phase8
```

Files:

- `traces.jsonl`: one record per exported run.
- `grounding_eval.jsonl`: one record per exported click action with screenshot path, target, coordinate, bbox, source, stage, and verdict.
- `fewshot_examples.jsonl`: prompt examples derived from successful IM and Docs runs.
- `export_summary.json`: machine-readable export summary.
- `export_summary.md`: human-readable export summary.
- `mcp_manifest.json`: MCP-ready manifest generated from the local tool registry.

Default export status is `pass`. Manual buckets must be explicitly requested:

```bash
python -m cua_lark.main export-traces runs --out datasets/generated/manual --statuses pass,needs_manual_verification
```
