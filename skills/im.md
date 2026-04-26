# IM Skill

## 常见入口

- 左侧栏通常包含消息入口。
- 顶部搜索框可搜索联系人、群聊和聊天记录。
- Phase 2A 临时使用固定坐标锚点，坐标会按当前屏幕尺寸缩放。

## 发送文本流程

1. 聚焦飞书窗口，或由用户使用 `--assume-frontmost-window` 手动确认飞书在前台。
2. 截图并记录 `before_coordinate_plan.png`。
3. 规划消息入口、搜索框、首个搜索结果、输入框和发送动作坐标。
4. 点击消息入口。
5. 点击搜索框。
6. 粘贴测试群名 `CUA-Lark-Test`。
7. 按 Enter 打开测试群。
8. 点击底部输入框。
9. 粘贴包含 `CUA-Lark` 和唯一 `run_id` 的消息。
10. 最终发送前再次执行 SafetyGuard。
11. 只有 `--allow-send` 存在时才按 Enter 发送。

## Dry Run 规则

`--dry-run` 可以执行窗口聚焦、截图、坐标规划和 trace 记录，但不得输入、粘贴或发送。报告最终状态应为 `uncertain`，用于人工确认坐标和动作计划。

## 常见异常

- 找不到飞书窗口：返回 blocked；用户可手动置前后使用 `--assume-frontmost-window`。
- 坐标超出屏幕：返回 blocked，不执行点击。
- confirm-target 与 chat_name 不一致：返回 blocked。
- 消息缺少 `CUA-Lark` 或 `run_id`：返回 blocked。
- 没有 OCR/VLM/API 证据：真实发送后仍需要人工复核。
