# 最终交付 Checklist

本文档用于最终提交、答辩和复现检查。默认不执行真实飞书操作；真实 smoke 命令只在需要端到端验收时运行。

## 1. 基线检查

```powershell
git status --short --branch
.\.conda310\python.exe -m pytest tests
```

期望：

- 工作区干净。
- 全量测试通过。

## 2. Mock 评测

```powershell
.\.conda310\python.exe -m cua_lark.main eval testcases\eval\feishuworld_mock.yaml --profile mock --runs-dir runs
```

检查最新输出目录中存在：

- `summary.json`
- `summary.md`
- `summary.html`
- 每个 case 的 `trace.jsonl`
- 每个 case 的 `report.md`

## 3. 真实 Smoke 基线

真实 smoke 会发送飞书测试群消息并创建云文档：

```powershell
.\.conda310\python.exe -m cua_lark.main eval testcases\eval\feishuworld_real_smoke.yaml --profile real-smoke --runs-dir runs
```

已验证通过的基线报告：

```text
runs\feishuworld_real_smoke_real-smoke_20260506_173201_138632\summary.md
```

稳定真实链路：

- `im_send_text_real`：在 `CUA-Lark-Test` 群发送带 run_id 的消息。
- `docs_create_blank_doc_real`：创建带唯一标题的云文档。

## 4. Phase 8 数据导出

```powershell
.\.conda310\python.exe -m cua_lark.main export-traces runs --out datasets\generated\feishuworld_phase8 --include-products im,docs --max-runs 10
```

检查输出：

- `traces.jsonl`
- `grounding_eval.jsonl`
- `fewshot_examples.jsonl`
- `export_summary.json`
- `export_summary.md`
- `mcp_manifest.json`

失败样本复盘可选：

```powershell
.\.conda310\python.exe -m cua_lark.main export-traces runs --out datasets\generated\failure_analysis --statuses blocked,fail,uncertain --max-runs 10
```

## 5. 演示顺序

1. README：项目定位和快速验收命令。
2. `docs/demo_script.md`：按 5 分钟脚本介绍。
3. `summary.html`：展示指标、case、trace/report/截图路径。
4. 单 case `report.md`：展示每步 action/verdict。
5. `trace.jsonl`：展示可复现原始轨迹。
6. Phase 8 导出目录：展示 JSONL 数据资产和 `mcp_manifest.json`。

## 6. 最终 Git 操作

```powershell
git checkout main
git merge --no-ff feat/phase8-trace-tooling -m "Merge Phase 8 trace tooling"
git push origin main
git tag phase8-final
git push origin phase8-final
```

确认：

- `main` 包含 Phase 8 和最终文档。
- tag `phase8-final` 指向最终提交。
- `runs/` 和 `datasets/generated/` 没有进入版本库。
