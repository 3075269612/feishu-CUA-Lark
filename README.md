# CUA-Lark

CUA-Lark 是一个面向飞书 / Lark 桌面端的视觉优先 CUA（Computer-Use Agent）智能测试代理工程骨架。当前阶段已完成 Phase 0 / Phase 1 / Phase 2，并进入 Phase 3 收口：将 VLM bbox、OCR 文本框和 Accessibility Tree 候选组合成混合定位链路。

长期目标是让 Agent 通过截图理解飞书界面，通过鼠标键盘完成真实用户操作，并结合视觉、OCR、Accessibility Tree 和飞书 OpenAPI 做多重验证。飞书 OpenAPI 只作为验收 Oracle 和测试数据准备工具，不作为主执行路径。

## 当前能力

已实现：

- YAML `TaskSpec` 加载。
- 测试群、联系人、文档目录、日历关键词和高风险动作的 SafetyGuard。
- mock Planner / Actor / Verifier 闭环。
- Phase 2A 真实 UI 执行入口：窗口聚焦、截图、固定坐标规划、trace 记录。
- `--dry-run` 安全验收模式：不输入、不粘贴、不发送。
- `--allow-send` 显式开关：只在用户确认后执行最后发送动作。
- Phase 2B IM verifier chain：截图证据、任务验收项、API/OCR/VLM 可插拔占位。
- Verification Summary：报告 verifier 子状态、证据版本、人工复核清单。
- Phase 3 hybrid grounding：真实 UI 路径使用 VLM bbox + OCR + Accessibility Tree 进行坐标定位和结构候选吸附。
- Accessibility Tree 只作为视觉定位增强，不替代截图/VLM 主决策；飞书 OpenAPI 只作为验证 Oracle，不替代桌面端操作。
- 每次运行生成 `runs/<task_id>_<timestamp>/` trace 目录。
- Markdown 报告生成。
- VLM、OCR、Accessibility、桌面动作和飞书 API 的可导入接口。

暂未实现：

- Calendar / Docs 的真实桌面端工作流。
- FeishuWorld 批量评测集和 HTML Dashboard。
- MCP、OpenCLI 主路径、GUI-R1 / ScaleCUA 微调。

## 本地参考资料

以下文件只作为本地参考资料，不应提交进 git，除非后续明确要求：

- `CUA-Lark.pdf`
- `最终方案.docx`
- `CUA-Lark · 让大模型像人一样操作飞书桌面端 .docx`

这些文件已在 `.gitignore` 中忽略。

## 快速开始

```bash
D:/2026上/feishu-CUA-Lark/.venv/Scripts/python.exe -m pytest
D:/2026上/feishu-CUA-Lark/.venv/Scripts/python.exe -m cua_lark.main run testcases/im/send_text.yaml --mock
D:/2026上/feishu-CUA-Lark/.venv/Scripts/python.exe -m cua_lark.main run testcases/im/send_text.yaml --real-ui --confirm-target CUA-Lark-Test --dry-run
```

mock 运行会生成类似目录：

```text
runs/im_send_text_001_20260425_120000/
  task.yaml
  trace.jsonl
  step_001.json
  report.md
```

## 后续路线

1. Phase 0：测试环境、测试租户、allowlist 和安全凭证。
2. Phase 1：原子操作接口和 mock 闭环。
3. Phase 2：真实 IM 发消息闭环。
4. Phase 3：VLM bbox + OCR + Accessibility 的混合定位（已基本实现，当前分支用于验证与收口）。
5. Phase 4：Calendar 日程工作流。
6. Phase 5：Docs 文档工作流。
7. Phase 6：跨产品链路。
8. Phase 7：评测集、回放和更完整的报告。

## Phase 2A 真实 UI 安全开关

真实桌面模式默认不发送消息。推荐验收顺序：

```bash
D:/2026上/feishu-CUA-Lark/.venv/Scripts/python.exe -m cua_lark.main run testcases/im/send_text.yaml --mock
D:/2026上/feishu-CUA-Lark/.venv/Scripts/python.exe -m cua_lark.main run testcases/im/send_text.yaml --real-ui --confirm-target CUA-Lark-Test --dry-run
D:/2026上/feishu-CUA-Lark/.venv/Scripts/python.exe -m cua_lark.main run testcases/im/send_text.yaml --real-ui --confirm-target CUA-Lark-Test --allow-send --assume-frontmost-window
```

安全约束：

- `--real-ui` 才会启用真实桌面后端。
- `--grounding hybrid` 使用视觉优先的混合定位，不新增其它公开定位模式。
- `--confirm-target CUA-Lark-Test` 必须与测试用例中的 `chat_name` 完全一致。
- 只有显式传入 `--allow-send`，最后一步才允许按 Enter 发送。
- `--dry-run` 不输入、不粘贴、不发送，只记录计划动作、坐标和截图。
- 真实发送后会进入 verification step；只有 OCR/VLM/API oracle 等自动验证明确通过时才给自动 `pass`。
- 真实 UI 发送链路不使用固定坐标完成消息入口或会话列表定位；定位失败必须阻断或只使用明确安全的消息输入区几何回退。
- `--strict-verification` 下只有自动 `pass` 返回 0，其它状态全部返回非 0。
- 项目默认解释器固定为 `D:/2026上/feishu-CUA-Lark/.venv/Scripts/python.exe`。
- 不需要 editable install；测试依赖缺失时只安装 `pytest`、`pydantic`、`PyYAML`。
