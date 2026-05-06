# 决赛演示脚本

目标：用 5 分钟展示 CUA-Lark 是一个视觉优先、可验证、可复现的飞书桌面端智能测试代理。

配套材料：

- 最终交付检查：`docs/final_delivery_checklist.md`
- 引用来源与自研说明：`docs/references_and_innovation.md`
- 失败复盘：`docs/failure_analysis.md`

## 0:00 - 0:30 项目定位

CUA-Lark 不是飞书 API 自动化脚本，也不是泛化电脑 Agent。它面向飞书桌面端，通过截图理解 UI，通过鼠标键盘完成真实用户操作，再用视觉、OCR、Accessibility Tree 和飞书 OpenAPI 做多重验证，最后生成 trace 和评测报告。

强调边界：

- 主操作路径是桌面 UI。
- API 只做 Oracle，不替代操作。
- 真实稳定 smoke 覆盖 IM 发消息和 Docs 创建标题文档。

## 0:30 - 2:30 真实 Smoke 展示

运行：

```powershell
python -m cua_lark.main eval testcases\eval\feishuworld_real_smoke.yaml --profile real-smoke --runs-dir runs
```

展示点：

- IM：打开测试群 `CUA-Lark-Test`，发送带 run_id 的消息。
- Docs：点击 `云文档`，点击主页 `新建` 按钮，选择 `文档`，再点 `新建空白文档`，输入唯一标题。
- 两个 case 都生成独立 trace 目录和 report。

如果现场不方便真实执行，可以打开已保存的真实 smoke 报告：

```text
runs\<real-smoke-suite-dir>\summary.md
```

## 2:30 - 3:30 报告与证据

展示：

- `summary.json`：机器可读指标。
- `summary.md`：评测摘要。
- `summary.html`：轻量展示页，包含 trace、report 和截图路径入口。
- 单 case `report.md`：步骤、状态、验证证据。
- `trace.jsonl`：每步 observation、action、verdict。

关键指标：

- `task_success_rate`
- `step_success_rate`
- `mean_steps`
- `mean_time`
- `failure_category`
- `visual_api_agreement`

## 3:30 - 4:30 Trace 数据资产

运行：

```powershell
python -m cua_lark.main export-traces runs --out datasets\generated\feishuworld_export --include-products im,docs --max-runs 10
```

展示：

- `traces.jsonl`
- `grounding_eval.jsonl`
- `fewshot_examples.jsonl`
- `export_summary.md`
- `mcp_manifest.json`

说明：这些数据为后续 few-shot、grounding eval、小规模 SFT 或 GUI-R1 风格奖励实验做准备，但当前项目不宣称已训练模型。

## 4:30 - 5:00 技术取舍

强调：

- UI-TARS、UGround、OSWorld、GUI-R1、ScaleCUA 等是参考思想，不是运行时依赖。
- OpenCLI / MCP 全部后置；当前只做 local tool registry 和 MCP-ready manifest。
- 项目的核心价值是工程闭环：视觉操作、状态验证、批量评测、可复现 trace。

## 备用命令

Mock 快速回归：

```powershell
python -m cua_lark.main eval testcases\eval\feishuworld_mock.yaml --profile mock --runs-dir runs
```

全量单测：

```powershell
python -m pytest tests
```
