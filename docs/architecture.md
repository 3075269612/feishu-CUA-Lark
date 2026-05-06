# 架构

CUA-Lark 采用七模块架构，目标是逐步构建一个视觉优先的飞书桌面端智能测试代理。

1. TaskSpec：把 YAML 测试用例和自然语言指令变成受控任务规格。支持 `--nl` 参数传入自然语言，由 VLM（Qwen-VL-Max）结合 `skills/*.md` 领域知识自动解析为 TaskSpec JSON。
2. Planner：结合任务和 Feishu Skills 生成小步目标，避免一次性生成脆弱长路径。Phase 6 新增 `CrossProductSkill` 元状态机，显示子任务状态机串联 IM、Calendar、Docs，禁止模型自由控制长链路。
3. Perceptor：负责截图；后续会接入 VLM、OCR、Accessibility Tree。
4. Grounder：把“点击消息输入框”这类目标转为坐标。Phase 2A 暂用固定坐标 + 分辨率缩放，Phase 3 再做混合定位。
5. Actor：执行桌面动作。当前包含 mock 后端、dry-run 后端和 PyAutoGUI 后端。
6. Verifier：判断步骤结果。Phase 2B 提供 IM verifier chain，聚合截图证据、任务验收项、API/OCR/VLM 占位证据。
7. Trace/Report：记录 observation、action、verdict、截图、坐标来源和报告。

## 当前执行模式

- `--mock`：Phase 1 安全闭环，不触碰真实桌面。
- `--real-ui --dry-run`：聚焦、截图、规划坐标和记录 trace，不输入、不粘贴、不发送。
- `--real-ui --allow-send`：通过三层安全门禁后，最后一步才允许发送。
- `--nl <自然语言>`：使用 VLM 将自然语言指令自动解析为 TaskSpec，代替手写 YAML 文件。
- `--strict-verification`：只有自动验证 pass 才返回成功退出码。

## 新产品支持

- **Calendar**：`CalendarCreateSkill` 6 阶段状态机（导航→创建→标题→保存→验证→Done）
- **Docs**：`DocsCreateSkill` 5 阶段状态机（云文档→新建→文档类型→新建空白→标题）
- **Cross-Product**：`CrossProductSkill` 元状态机串联 Calendar→Docs→IM，每阶段委派给对应子状态机

## 原则

- 视觉优先：主路径最终必须基于截图和 VLM 理解。
- 结构辅助：OCR、Accessibility Tree、Touchpoint 只增强定位和验证。
- API 验收：飞书 OpenAPI 只用于准备数据和最终状态验证，不替代桌面 UI 操作。
- Trace-first：每一步都必须留下可复盘证据。
- Safety-first：真实发送必须显式确认目标和发送开关。
- NL-first：支持自然语言输入，VLM 自动解析为 TaskSpec，降低测试用例编写门槛。
