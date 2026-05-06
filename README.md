# CUA-Lark

面向飞书 / Lark 桌面端的视觉优先 CUA（Computer-Use Agent）智能测试代理。Agent 通过截图理解界面，通过鼠标键盘完成真实用户操作，结合视觉、OCR、Accessibility Tree 和飞书 OpenAPI 做多重验证。

## 架构

```
用户自然语言 / YAML 测试用例
        │
        ▼
1. TaskSpec ── 任务解析（NL→JSON 或 YAML→TaskSpec）
2. Planner  ── 状态机驱动，分步规划
3. Perceptor ── 截图 + VLM 摘要 + OCR + Accessibility Tree
4. Grounder  ── VLM bbox + OCR + Accessibility 混合定位
5. Actor    ── PyAutoGUI / dry-run / mock 三后端
6. Verifier ── 截图 + API Oracle + OCR + VLM 四源验证
7. Trace    ── 每步截图、坐标、判决落盘，生成 Markdown 报告
```

## 产品覆盖

| 产品 | YAML 用例 | NL 自然语言 | 真实 UI 验证 |
|------|-----------|-------------|-------------|
| IM | `testcases/im/` | `--nl "在CUA-Lark-Test群发消息"` | ✅ |
| Calendar | `testcases/calendar/` | `--nl "创建CUA-Lark日程"` | ✅ |
| Docs | `testcases/docs/` | `--nl "创建CUA测试文档"` | ✅ |
| Cross-Product | `testcases/cross_product/` | `--nl "执行CUA-Lark启动流程"` | ✅ |

## 快速开始

```bash
# 安装依赖
pip install pytest pydantic PyYAML

# 运行测试
python -m pytest

# Mock 模式（安全，不操作桌面）
python -m cua_lark.main run testcases/im/send_text.yaml --mock
python -m cua_lark.main run --nl "在CUA-Lark-Test群发一条消息" --mock

# 真实 UI（逐级放行）
python -m cua_lark.main run testcases/im/send_text.yaml --real-ui --confirm-target CUA-Lark-Test --dry-run
python -m cua_lark.main run testcases/im/send_text.yaml --real-ui --confirm-target CUA-Lark-Test --allow-send
python -m cua_lark.main run --nl "在CUA-Lark-Test群发消息：测试" --real-ui --confirm-target CUA-Lark-Test --allow-send
```

## 安全模式

| 模式 | 桌面操作 | 适用场景 |
|------|---------|---------|
| `--mock` | 无 | 回归测试、CI |
| `--real-ui --dry-run` | 截图+分析，不输入 | 人工审核计划 |
| `--real-ui --allow-send` | 完整操作+发送 | 端到端验证 |

安全约束详见 `docs/safety.md`，allowlist 配置在 `configs/safety.yaml`。

## 路线图

1. Phase 0：环境与安全边界 ✅
2. Phase 1：原子操作与 mock 闭环 ✅
3. Phase 2：真实 IM 执行与验证 ✅
4. Phase 3：VLM + OCR + Accessibility 混合定位 ✅
5. Phase 4：Calendar 日程状态机 ✅
6. Phase 5：Docs 文档创建与编辑 ✅
7. Phase 6：跨产品链路 + NL→TaskSpec ✅
8. Phase 7：评测集与报告（待开发）

## 目录结构

```
cua_lark/
  task/         TaskSpec 定义、YAML 加载、NL 解析
  agent/        Planner、SafetyGuard、Recovery、Memory
  perception/   截图、VLM、OCR、Accessibility
  grounding/    混合定位（VLM + OCR + Accessibility）
  actions/      PyAutoGUI / dry-run / mock 后端
  verifier/     IM 验证链（截图 + API + OCR + VLM）
  calendar/     CalendarCreateSkill 状态机
  docs/         DocsCreateSkill 状态机
  cross_product/ CrossProductSkill 元状态机
  feishu/       飞书 OpenAPI 客户端
  trace/        运行记录与回放
  report/       Markdown 报告生成
configs/        桌面、模型、安全、密钥配置
skills/         飞书各产品操作手册（Markdown）
testcases/      YAML 测试用例
docs/           架构、路线图、安全策略文档
```
