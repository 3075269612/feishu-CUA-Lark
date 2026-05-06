# CUA-Lark

CUA-Lark 是一个面向飞书 / Lark 桌面端的视觉优先 CUA（Computer-Use Agent）智能测试代理。它通过截图理解界面，通过鼠标键盘执行真实用户操作，再结合 OCR、Accessibility Tree、VLM 和飞书 OpenAPI Oracle 验证结果，并为每次运行留下可复现 trace 与评测报告。

项目目标不是把飞书 API 包装成自动化脚本，而是建立一套可复现、可审计的桌面端 GUI 测试框架：自然语言或 YAML 用例进入任务解析器，Agent 观察屏幕、定位目标、执行动作、验证结果，最后输出结构化评测数据。

## 安装

建议使用 Python 3.10+ 的虚拟环境。

```powershell
python -m pip install -e .
python -m pytest tests
```

运行真实桌面 UI 前，需要：

- 安装并登录飞书 / Lark 桌面客户端。
- 准备测试群、测试文档空间和测试账号。
- 根据 `configs/*.yaml` 配置桌面、安全和飞书验证项。
- 将飞书 OpenAPI token 放在本地环境或未提交的本地配置中，不要提交密钥。

## 快速验收

下面三条命令不会执行真实发送或真实文档创建，适合作为本地回归和仓库验收入口。

```powershell
# 全量单测
python -m pytest tests

# Mock FeishuWorld suite：安全、可重复，生成 summary.json/md/html
python -m cua_lark.main eval testcases\eval\feishuworld_mock.yaml --profile mock --runs-dir runs

# Trace 数据导出：不复制截图，只记录路径和元数据
python -m cua_lark.main export-traces runs --out datasets\generated\feishuworld_export --include-products im,docs --max-runs 10
```

真实 smoke suite 会真实发送测试群消息并创建新的云文档，只在端到端验收时运行：

```powershell
python -m cua_lark.main eval testcases\eval\feishuworld_real_smoke.yaml --profile real-smoke --runs-dir runs
```

## 核心架构

```text
自然语言 / YAML 测试用例
        |
        v
TaskSpec  受控任务规格
Planner   状态机与技能驱动的步骤规划
Perceptor 截图 + VLM 摘要 + OCR + Accessibility Tree
Grounder  VLM bbox + OCR + Accessibility 混合定位
Actor     PyAutoGUI / dry-run / mock 后端
Verifier  截图 + API Oracle + OCR + VLM 分层验证
Trace     observation / action / verdict 落盘
Eval      suite 批量运行与聚合报告
Export    JSONL 数据集与 MCP-ready manifest
```

## 支持能力

| 能力 | 状态 |
| --- | --- |
| 视觉感知 | 截图、VLM 摘要、OCR 文本、Accessibility Tree 候选。 |
| 自然语言任务 | `--nl` 将自然语言解析为 `TaskSpec`，YAML 用例也可直接运行。 |
| 基础 GUI 动作 | 单击、双击、右键、拖拽、滚动、文本粘贴、按键、快捷键组合、窗口聚焦。 |
| 混合定位 | VLM bbox 优先，OCR 和 Accessibility 候选用于吸附、校正和证据记录。 |
| 状态验证 | IM API/OCR/VLM verifier、Docs 后置视觉验证、报告中的 manual bucket。 |
| Trace-first | 每步记录 observation、action、verdict、截图路径、坐标来源和证据。 |
| 批量评测 | 读取 suite YAML，逐 case 运行，生成 `summary.json`、`summary.md`、`summary.html`。 |
| 数据导出 | 从成功 trace 导出 `traces.jsonl`、`grounding_eval.jsonl`、`fewshot_examples.jsonl`。 |

## 产品覆盖

| 产品 | 用例目录 | Mock / Eval | 真实 smoke 口径 |
| --- | --- | --- | --- |
| IM | `testcases/im/` | 已覆盖 | 稳定链路：在 allowlist 测试群发送带唯一 run_id 的消息。 |
| Docs | `testcases/docs/` | 已覆盖 | 稳定链路：创建带唯一标题的云文档。 |
| Calendar | `testcases/calendar/` | 已覆盖 | 保留状态机和 mock 评测，不作为默认真实 smoke 链路。 |
| Cross-Product | `testcases/cross_product/` | 已覆盖 | 保留跨产品状态机和 mock 评测，不作为默认真实 smoke 链路。 |

真实稳定 smoke suite 固定为 IM + Docs，避免把容易受 UI 状态影响的链路混入默认通过率。

## 运行模式

| 模式 | 桌面操作 | 适用场景 |
| --- | --- | --- |
| `--mock` | 无 | CI、回归、文档演示。 |
| `--real-ui --dry-run` | 聚焦、截图、分析，不输入不发送。 | 人工审核计划。 |
| `--real-ui --allow-send` | 完整真实 UI 操作。 | 端到端 smoke 验收。 |

真实 UI 必须提供 `--confirm-target`，并受 `configs/safety.yaml` allowlist 约束。飞书 OpenAPI 只做 Oracle 验证，不替代桌面 UI 完成任务。

## 评测与报告

`eval` 会为每个 case 复用现有 `run` 路径执行，再聚合输出：

- `summary.json`：机器可读指标。
- `summary.md`：Markdown 汇总。
- `summary.html`：轻量 HTML 展示页，包含 case、trace、report 和截图路径入口。
- 单 case `report.md`：步骤、状态、验证证据。
- 单 case `trace.jsonl`：完整 observation/action/verdict 轨迹。

核心指标包括：

- `task_success_rate`
- `step_success_rate`
- `mean_steps`
- `mean_time`
- `recovery_count`
- `failure_category`
- `visual_api_agreement`

## Trace 数据导出

`export-traces` 将 `runs/` 中的 trace 转为可复用 JSONL 数据资产，并生成本地 tool registry 的 MCP-ready manifest。

```powershell
python -m cua_lark.main export-traces runs --out datasets\generated\feishuworld_export
python -m cua_lark.main export-traces runs --out datasets\generated\manual --statuses pass,needs_manual_verification --include-products im,docs
```

输出：

- `traces.jsonl`
- `grounding_eval.jsonl`
- `fewshot_examples.jsonl`
- `export_summary.json`
- `export_summary.md`
- `mcp_manifest.json`

默认只导出 `pass`。`datasets/generated/` 被 Git 忽略，避免提交真实路径、截图引用或本地运行数据。

## 目录结构

```text
cua_lark/
  task/          TaskSpec、YAML 加载、NL 解析
  agent/         Planner、SafetyGuard、Recovery、Memory
  perception/    截图、VLM、OCR、Accessibility
  grounding/     混合定位
  actions/       PyAutoGUI / dry-run / mock 后端
  verifier/      API/OCR/VLM 验证模块
  calendar/      Calendar 状态机
  docs/          Docs 状态机
  cross_product/ Cross-product 元状态机
  eval/          suite runner、metrics、report
  trace/         运行记录、导出器、回放占位
  report/        单 run Markdown 报告
  feishu/        飞书 OpenAPI 客户端
configs/         桌面、模型、安全、飞书配置
skills/          飞书产品操作手册
testcases/       YAML 测试用例和 eval suite
datasets/        数据集说明；generated/ 默认不提交
docs/            架构、交付、复盘、安全和路线图
tests/           单元测试与 CLI 回归测试
```

## 文档索引

- [架构说明](docs/architecture.md)
- [基础操作能力说明](docs/action_capabilities.md)
- [安全策略](docs/safety.md)
- [决赛演示脚本](docs/demo_script.md)
- [失败复盘](docs/failure_analysis.md)
- [引用来源与自研创新说明](docs/references_and_innovation.md)
- [Trace Tooling](docs/trace_tooling.md)
- [路线图](docs/roadmap.md)

## 参考与边界

UI-TARS、UGround、OSWorld、GUI-R1、ScaleCUA、ScenGen、Touchpoint、OpenCLI 和 MCP 主要作为方案思想参考。当前代码没有把这些项目作为运行时硬依赖；真实落地的是视觉优先闭环、混合定位、Skills、Trace-first、FeishuWorld 评测和 Trace 数据导出。
