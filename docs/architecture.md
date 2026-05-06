# 架构

CUA-Lark 是一个视觉优先的飞书 / Lark 桌面端智能测试框架。主路径坚持“看屏幕、做操作、验状态、留证据”，飞书 OpenAPI 只作为 Oracle 验证来源，不替代桌面 UI 操作。

## 模块

1. **TaskSpec**：把 YAML 测试用例和自然语言指令变成受控任务规格。`--nl` 会调用 VLM 结合 `skills/*.md` 生成 TaskSpec JSON。
2. **Planner / Skills**：结合任务、产品技能和显式状态机生成小步目标。IM、Calendar、Docs 和 Cross-Product 都有可复用规划路径。
3. **Perceptor**：采集截图，并提取 VLM 摘要、OCR 文本和 Accessibility Tree 候选。
4. **Grounder**：把“点击消息输入框”这类语义目标转成坐标。当前使用 VLM bbox、OCR 文本框和 Accessibility 候选的混合定位。
5. **Actor**：执行桌面动作。当前包含 mock、dry-run 和 PyAutoGUI 后端，支持单击、双击、右键、拖拽、滚动、文本粘贴、按键和快捷键组合。
6. **Verifier**：判断步骤或任务结果。IM 使用截图、任务验收项、OpenAPI、OCR 和 VLM 的 verifier chain；Docs 使用后置视觉验证。
7. **Trace / Report**：记录 observation、action、verdict、截图、坐标来源和报告。
8. **Eval / Export**：批量运行 suite，生成聚合报告，并把成功 trace 导出为 JSONL 数据资产。

## 执行模式

- `--mock`：安全回归模式，不触碰真实桌面。
- `--real-ui --dry-run`：聚焦、截图、规划坐标和记录 trace，不输入、不粘贴、不发送。
- `--real-ui --allow-send`：通过安全门禁后执行真实 UI 操作。
- `--nl <自然语言>`：使用 VLM 将自然语言指令解析为 TaskSpec，代替手写 YAML 文件。
- `--strict-verification`：只有自动验证 `pass` 才返回成功退出码。

## 产品状态机

- **IM**：打开消息模块、定位测试群、粘贴消息、发送并验证。
- **Calendar**：导航日历、创建日程、填写标题、保存、验证。
- **Docs**：进入云文档、点击新建、选择文档、创建空白文档、填写唯一标题、验证。
- **Cross-Product**：用元状态机串联 Calendar、Docs 和 IM 汇总，不让模型自由控制长链路。

## 原则

- 视觉优先：主路径基于截图和视觉语义理解。
- 结构辅助：OCR 和 Accessibility Tree 用于增强定位与验证。
- API 验收：飞书 OpenAPI 只做最终状态验证和证据补充。
- Trace-first：每一步都留下可复盘证据。
- Safety-first：真实发送和真实创建必须显式确认目标和执行开关。
- NL-first：支持自然语言输入，降低测试用例编写门槛。
