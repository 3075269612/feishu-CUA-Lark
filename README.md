# CUA-Lark

CUA-Lark 是一个面向飞书 / Lark 桌面端的视觉优先 CUA（Computer-Use Agent）智能测试代理。它通过截图理解界面，通过鼠标键盘完成真实用户操作，再结合 OCR、Accessibility Tree、VLM 和飞书 OpenAPI Oracle 验证结果，并为每次运行留下可复现 trace 与评测报告。

项目主线已经完成 Phase 0-8：从安全边界、IM 闭环、混合定位、Calendar / Docs / Cross-Product 状态机，到 FeishuWorld 评测集、Phase 8 trace 数据导出和 MCP-ready tool registry。

## 快速验收

建议按下面顺序验收。除 `real-smoke` 外，其余命令不会操作真实飞书 UI。

```powershell
# 1. 全量单测
.\.conda310\python.exe -m pytest tests

# 2. Mock FeishuWorld suite：安全、可重复、生成 summary.json/md/html
.\.conda310\python.exe -m cua_lark.main eval testcases\eval\feishuworld_mock.yaml --profile mock --runs-dir runs

# 3. Phase 8 trace 数据导出：不复制截图，只记录路径和元数据
.\.conda310\python.exe -m cua_lark.main export-traces runs --out datasets\generated\feishuworld_phase8 --include-products im,docs --max-runs 10
```

真实 smoke suite 会真实发送测试群消息并创建新的云文档，只在需要端到端验收时运行：

```powershell
.\.conda310\python.exe -m cua_lark.main eval testcases\eval\feishuworld_real_smoke.yaml --profile real-smoke --runs-dir runs
```

最近一次已验证通过的真实报告路径：

```text
runs\feishuworld_real_smoke_real-smoke_20260506_173201_138632\summary.md
```

## 核心架构

```text
用户自然语言 / YAML 测试用例
        |
        v
1. TaskSpec  任务解析（NL -> TaskSpec 或 YAML -> TaskSpec）
2. Planner   状态机驱动，按场景推进
3. Perceptor 截图 + VLM 摘要 + OCR + Accessibility Tree
4. Grounder  VLM bbox + OCR + Accessibility 混合定位
5. Actor     PyAutoGUI / dry-run / mock 后端
6. Verifier  截图 + API Oracle + OCR + VLM 分层验证
7. Trace     每步 observation/action/verdict 落盘
8. Eval      FeishuWorld suite 聚合报告
9. Export    Phase 8 JSONL 数据集与 MCP-ready manifest
```

## 产品覆盖

| 产品 | 用例目录 | Mock / Eval | 真实 smoke 口径 |
| --- | --- | --- | --- |
| IM | `testcases/im/` | 已覆盖 | 稳定链路：在 `CUA-Lark-Test` 测试群发送带 run_id 的消息 |
| Docs | `testcases/docs/` | 已覆盖 | 稳定链路：创建带唯一标题的云文档 |
| Calendar | `testcases/calendar/` | 已覆盖 | 保留状态机和 mock 评测，不作为最终 real-smoke 稳定口径扩写 |
| Cross-Product | `testcases/cross_product/` | 已覆盖 | 保留元状态机和 mock 评测，不作为最终 real-smoke 稳定口径扩写 |

真实稳定 smoke suite 固定为 IM + Docs，避免把不稳定 UI 链路混入最终通过率叙事。

## 运行模式

| 模式 | 桌面操作 | 适用场景 |
| --- | --- | --- |
| `--mock` | 无 | CI、回归、文档演示 |
| `--real-ui --dry-run` | 聚焦、截图、分析，不输入不发送 | 人工审核计划 |
| `--real-ui --allow-send` | 完整真实 UI 操作 | 端到端 smoke 验收 |

真实 UI 必须提供 `--confirm-target`，并受 `configs/safety.yaml` allowlist 约束。API 只做 Oracle 验证，不替代桌面 UI 完成任务。

## 评测与报告

`eval` 会为每个 case 复用现有 `run` 路径执行，再聚合输出：

- `summary.json`：机器可读指标。
- `summary.md`：Markdown 汇总。
- `summary.html`：轻量 HTML 展示页，包含 case、trace、report 和截图路径入口。
- 单 case `report.md`：步骤、状态、验证证据。
- 单 case `trace.jsonl`：完整 observation/action/verdict 轨迹。

核心指标：

- `task_success_rate`
- `step_success_rate`
- `mean_steps`
- `mean_time`
- `recovery_count`
- `failure_category`
- `visual_api_agreement`

## Phase 8 数据导出

`export-traces` 将 `runs/` 中的 trace 转为可复用 JSONL 数据资产，并生成本地 tool registry 的 MCP-ready manifest。

```powershell
.\.conda310\python.exe -m cua_lark.main export-traces runs --out datasets\generated\feishuworld_phase8
.\.conda310\python.exe -m cua_lark.main export-traces runs --out datasets\generated\manual --statuses pass,needs_manual_verification --include-products im,docs
```

输出：

- `traces.jsonl`
- `grounding_eval.jsonl`
- `fewshot_examples.jsonl`
- `export_summary.json`
- `export_summary.md`
- `mcp_manifest.json`

默认只导出 `pass`。`datasets/generated/` 被 Git 忽略，避免提交真实路径、截图引用或本地运行数据。

## 交付文档

- [最终交付 Checklist](docs/final_delivery_checklist.md)
- [决赛演示脚本](docs/demo_script.md)
- [失败复盘](docs/failure_analysis.md)
- [引用来源与自研创新说明](docs/references_and_innovation.md)
- [Phase 8 Trace Tooling](docs/phase8_trace_tooling.md)
- [基础操作能力说明](docs/action_capabilities.md)
- [安全策略](docs/safety.md)
- [路线图](docs/roadmap.md)

## 目录结构

```text
cua_lark/
  task/          TaskSpec、YAML 加载、NL 解析
  agent/         Planner、SafetyGuard、Recovery、Memory
  perception/    截图、VLM、OCR、Accessibility
  grounding/     混合定位（VLM + OCR + Accessibility）
  actions/       PyAutoGUI / dry-run / mock 后端
  verifier/      IM 验证链与 API/OCR/VLM 验证模块
  calendar/      CalendarCreateSkill 状态机
  docs/          DocsCreateSkill 状态机
  cross_product/ CrossProductSkill 元状态机
  eval/          FeishuWorld suite runner、metrics、report
  trace/         运行记录、导出器、回放占位
  report/        单 run Markdown 报告
  feishu/        飞书 OpenAPI 客户端
  tool_registry.py 本地工具注册表与 MCP-ready manifest
configs/         桌面、模型、安全、飞书配置
skills/          飞书产品操作手册
testcases/       YAML 测试用例和 eval suite
datasets/        数据集说明；generated/ 默认不提交
docs/            架构、交付、复盘、安全和路线图
tests/           单元测试与 CLI 回归测试
```

## 参考与边界

UI-TARS、UGround、OSWorld、GUI-R1、ScaleCUA、ScenGen、Touchpoint、OpenCLI 和 MCP 主要作为方案思想参考。当前代码没有把这些项目作为运行时硬依赖；真实落地的是视觉优先闭环、混合定位、Skills、Trace-first、FeishuWorld 评测和 Phase 8 数据导出。
