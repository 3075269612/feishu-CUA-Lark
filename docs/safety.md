# 安全策略

CUA-Lark 只能操作准备好的测试环境。真实桌面执行必须默认保守，任何不确定状态都应停止或降级为人工复核。

## Allowlist

`configs/safety.yaml` 控制：

- `allowed_chats`
- `allowed_contacts`
- `allowed_doc_folders`
- `allowed_calendar_keywords`
- `forbidden_actions`
- `require_run_id_in_message`
- `real_ui_requires_confirm_target`

任务或动作目标不在 allowlist 内时必须 blocked。

## 真实 UI 三层开关

真实发送必须同时满足：

1. `--real-ui`：启用真实桌面后端。
2. `--confirm-target CUA-Lark-Test`：确认目标测试群，且必须与 `TaskSpec.slots.chat_name` 完全一致。
3. `--allow-send`：允许最后一步发送。

没有 `--allow-send` 时，流程最多进行窗口聚焦、截图、坐标规划、trace 记录和 dry-run，不得执行最终 Enter 或发送按钮点击。

## 最终发送前二次检查

发送前必须再次确认：

- `task.product == im`
- `risk_level == low`
- `chat_name` 在 `allowed_chats`
- `confirm-target == chat_name`
- 渲染后的消息包含 `CUA-Lark`
- 渲染后的消息包含唯一 `run_id`
- 前序步骤没有 unresolved 的 `blocked`、`fail` 或 `uncertain`

任一条件不满足，必须 blocked，不能发送。

## 结果判定

Phase 2A 没有 OCR、VLM、Accessibility Tree 或 Feishu OpenAPI oracle，因此真实发送后不能标记强自动 `pass`。当前只允许：

- `sent_with_screenshot_evidence`
- `needs_manual_verification`
- `uncertain`
- `blocked`

## Token 与截图隐私

API token 只能放在 `.env`，不能提交。`runs/` 包含截图、trace 和报告，默认被 git 忽略。共享前必须人工脱敏。

## 禁止行为

禁止给外部联系人发消息、邀请外部用户、公开分享链接、删除真实文档、群发或绕过桌面 UI 直接完成任务。
