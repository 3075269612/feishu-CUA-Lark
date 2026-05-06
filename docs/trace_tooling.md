# Trace Tooling

Trace tooling 的目标是把已经跑通的 FeishuWorld trace 变成可复用数据资产，并为后续工具化和模型优化留出稳定接口。它不扩展真实 UI 功能，不接入新的运行时底座，也不做真实微调。

最终交付入口见 `docs/final_delivery_checklist.md`；失败样本复盘见 `docs/failure_analysis.md`。

## 命令

```bash
python -m cua_lark.main export-traces runs --out datasets/generated/feishuworld_export
```

可选过滤：

```bash
python -m cua_lark.main export-traces runs --out datasets/generated/manual --statuses pass,needs_manual_verification --include-products im,docs --max-runs 20
```

默认只导出 `pass`。`needs_manual_verification` 和 `sent_with_screenshot_evidence` 必须显式加入 `--statuses`，避免把人工确认样本混入默认 few-shot 和 grounding eval。

## 输出

- `traces.jsonl`：run 级记录，包含任务、产品、状态、步骤摘要、验证证据和 trace 路径。
- `grounding_eval.jsonl`：点击级记录，包含截图路径、目标、坐标、bbox、定位来源、阶段和 verdict。
- `fewshot_examples.jsonl`：从成功 IM / Docs trace 生成的 prompt 示例。
- `export_summary.json` / `export_summary.md`：导出统计、产品分布、状态分布和生成文件位置。
- `mcp_manifest.json`：本地工具注册表的 MCP-ready manifest。

导出器只记录截图路径和元数据，不复制真实截图或二进制产物。`datasets/generated/` 默认被 `.gitignore` 忽略。

## Tool Registry

当前只实现本地 tool registry，不启动 MCP Server。固定工具名为：

- `feishuworld.eval.run_suite`
- `feishuworld.trace.export`
- `feishu.im.latest_message`
- `system.clipboard.set`

每个工具包含 `name`、`description`、`input_schema`、`output_schema`、`side_effects` 和 `implementation`。`mcp_manifest.json` 是后续 MCP 化的输入，不改变现有 `run` / `eval` 主路径。

## 与最终方案中项目/论文的关系

- UI-TARS / UGround：吸收视觉 grounding 到 bbox/坐标的思想；当前未接入其模型或 SDK。
- Touchpoint：吸收 Accessibility Tree 增强定位的思想；当前使用 Windows UI Automation 雏形，不依赖 Touchpoint。
- OpenCLI：仅作为环境准备、状态 dump、Electron/CDP 调试辅助的后置方向；不用于替代视觉点击完成任务。
- MCP：当前落到 tool registry 和 manifest；完整 MCP Server 后置。
- ScenGen：吸收场景驱动、监督和记录思想；当前不做多 Agent 复刻。
- GUI-R1 / ScaleCUA：当前只准备 trace 数据、few-shot 和 grounding eval；不做 SFT/RL。
- OSWorld：其真实环境、可复现评测和指标思想已经落到 FeishuWorld suite 与聚合报告。

## 验证

```bash
python -m pytest tests
```

Trace tooling 不要求再次真实操作飞书。真实 smoke 的验证基线来自已保存的 `feishuworld_real_smoke` suite。

失败样本可单独导出到 ignored 目录做复盘：

```bash
python -m cua_lark.main export-traces runs --out datasets/generated/failure_analysis --statuses blocked,fail,uncertain
```
