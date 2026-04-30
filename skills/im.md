# IM Skill

## 常见入口

- 左侧栏通常包含消息入口。
- 顶部搜索框可搜索联系人、群聊和聊天记录。
- Phase 2A 临时使用固定坐标锚点，坐标会按当前屏幕尺寸缩放。
- **Phase 2B 使用 VLM visual grounding**，依赖视觉大模型理解 UI 并定位元素。

## 发送文本流程（Phase 2B Visual Grounding）

**重要**：Phase 2B 主路径必须使用 VLM visual grounding，不要 fallback 到固定坐标。

**目标名称规范**：
- VLM 可以使用**中文或英文**描述 UI 元素，代码会自动映射到标准目标名称。
- 推荐使用自然的中文描述，例如"消息输入框"、"左侧消息按钮"等。
- 标准英文名称：`feishu_window`, `message_module`, `message_input`, `send_button_or_enter`

**生成 step goal 时的关键要求**：
- `target` 字段必须使用**实际的值**，而不是占位符或通用类型名称。
- ❌ 错误：`{"target": "chat_name"}` 或 `{"target": "chat_list_item"}`
- ✅ 正确：`{"target": "CUA-Lark-Test"}`（使用 `task.slots.chat_name` 的实际值）

示例 JSON：
```json
[
  {"index": 1, "description": "观察飞书窗口", "target": "feishu_window", "expected": "窗口可见"},
  {"index": 2, "description": "检查是否在消息页", "target": "message_module", "expected": "已在消息页或成功进入"},
  {"index": 3, "description": "打开CUA-Lark-Test群聊", "target": "CUA-Lark-Test", "expected": "群聊打开"},
  {"index": 4, "description": "粘贴消息到输入框", "target": "message_input", "expected": "消息已粘贴"}
]
```

流程步骤：

1. **聚焦飞书窗口**
   - 或由用户使用 `--assume-frontmost-window` 手动确认飞书在前台。
2. **观察当前 UI 状态**：使用 VLM 理解当前页面。
3. **智能导航到消息页**
   - 如果当前已在消息页（左侧会话列表可见），跳过此步骤。
   - 如果不在消息页，点击左侧导航栏的"消息"按钮。
4. **直接从左侧会话列表打开目标群聊**
   - 在左侧会话列表中找到目标群聊（如 `CUA-Lark-Test`）。
   - 点击该会话列表项打开群聊。
   - **不要使用全局搜索框**（顶部搜索框仅用于找不到会话的情况）。
5. **定位并点击底部输入框**
   - 使用 VLM 定位消息输入框。
6. **粘贴消息**：粘贴包含 `CUA-Lark` 和唯一 `run_id` 的消息。
7. **最终发送前再次执行 SafetyGuard**。
8. **只有 `--allow-send` 存在时才按 Enter 发送**。

## Phase 2A 固定坐标流程（Legacy）

仅用于 `--grounding fixed` 模式：

1. 聚焦飞书窗口。
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
- **VLM 找不到目标元素**：返回 blocked，不要 fallback 到危险的固定坐标。
