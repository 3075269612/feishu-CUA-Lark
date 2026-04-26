# 路线图

## Phase 0：环境与安全边界

准备测试租户、测试账号、测试群 `CUA-Lark-Test`、测试联系人、测试文档目录、日历关键词、桌面分辨率、登录态和 allowlist。

状态：已完成基础配置和 SafetyGuard。

## Phase 1：原子操作与 mock 闭环

完成 YAML 加载、安全检查、mock Planner / Actor / Verifier、trace 记录和 Markdown 报告。

状态：已完成，`--mock` 作为回归基线保留。

## Phase 2A：安全真实 IM 执行

目标是打通最小真实桌面链路：窗口聚焦、截图、固定坐标缩放、dry-run 记录、可选真实发送。

已实现：

- 三层开关：`--real-ui`、`--confirm-target`、`--allow-send`。
- `--dry-run` 不输入、不粘贴、不发送。
- 最终发送前二次 SafetyGuard。
- 坐标缩放、边界检查和 trace 元数据。
- 真实发送结果使用 `sent_with_screenshot_evidence`，不做自动强 pass。

## Phase 2B：IM 自动验证

接入 OCR 或 VLM 进行消息气泡验证，再接入飞书 OpenAPI optional oracle。只有视觉/OCR/API 证据足够时才升级为自动 pass/fail。

## Phase 3：混合定位

组合 VLM bbox、OCR 文本框和 Accessibility 候选。视觉定位优先，结构候选只用于坐标吸附和稳定性提升。

## Phase 4：Calendar

创建、修改、删除测试日程，标题必须包含 CUA-Lark allowlist 关键词。

## Phase 5：Docs

创建测试文档、编辑标题/正文，并验证文档元数据和内容。

## Phase 6：跨产品链路

用显式子任务状态机连接 IM、Calendar、Docs 和 IM 汇总，不允许让模型自由长链路操作。

## Phase 7：评测集与报告

构建 FeishuWorld 小型评测集，统计成功率、平均步数、耗时、恢复次数、失败分类和视觉/API 一致性。
