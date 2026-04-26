# ADR 0001：视觉优先 CUA

## 状态

Accepted.

## 背景

比赛要求 Agent 像真实用户一样理解并操作飞书桌面端。传统 API 自动化、DOM 选择器或单纯 Accessibility Tree 自动化可以提高效率，但无法体现 CUA 的核心能力，也容易在桌面 UI 变化时失效。

## 决策

CUA-Lark 的主路径采用视觉优先：

- 操作决策最终应来自截图和 VLM 理解。
- OCR、Accessibility Tree、Touchpoint 类结构化信息只作为定位增强和验证辅助。
- 飞书 OpenAPI 只作为测试数据准备和最终验收 oracle，不直接替代 UI 操作。
- OpenCLI、MCP、GUI-R1、ScaleCUA 作为后续增强，不进入 Phase 2A 主路径。

## Phase 2A 临时策略

为了先打通真实桌面闭环，Phase 2A 使用固定坐标 + 分辨率缩放作为临时定位方案。这不是最终架构，只用于验证窗口聚焦、截图、动作执行、trace 和安全门禁。

真实发送后的状态不标记强自动 pass，而是记录为 `sent_with_screenshot_evidence` 或 `needs_manual_verification`，等 Phase 2B/3 接入 OCR、VLM 或 API oracle 后再升级自动判定。

## 影响

- 项目优先建设 trace、报告和安全边界，再接入模型。
- 所有真实动作必须可复盘。
- API 和 CLI 工具不能绕过桌面 UI 完成主任务。
