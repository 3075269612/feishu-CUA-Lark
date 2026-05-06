# 基础操作能力说明

课题要求 CUA Agent 支持飞书桌面客户端的基础 GUI 操作。CUA-Lark 在 Backend 层提供统一动作接口，并分别支持 mock / dry-run / PyAutoGUI 真实后端。

## 已实现能力

| 能力 | Action type | Backend 方法 | 说明 |
| --- | --- | --- | --- |
| 单击 | `click` | `click(x, y, target)` | 主链路真实使用，用于点击导航、群聊、云文档、新建、标题区域等。 |
| 双击 | `double_click` | `double_click(x, y, target)` | 用于文件、文本或列表项的双击场景。 |
| 右键 | `right_click` | `right_click(x, y, target)` | 用于上下文菜单类场景；真实主链路默认不依赖右键。 |
| 拖拽 | `drag` | `drag(start_x, start_y, end_x, end_y, target, duration)` | 用于选择、移动或拖动类 GUI 场景。 |
| 滚动 | `scroll` | `scroll(clicks, x, y, target)` | 用于长列表、长文档和页面滚动。 |
| 文本输入 | `paste_text` | `paste_text(text)` | 通过剪贴板粘贴中文/英文/数字/run_id，规避输入法不稳定。 |
| 按键 | `press_key` | `press(key)` | 用于 Enter、Esc、方向键等键盘动作。 |
| 快捷键组合 | `hotkey` | `hotkey(*keys)` | 用于搜索、粘贴、页面操作和状态机导航。 |
| 截图 | observation metadata | `screenshot(path)` | 每步 observation、验证、报告和数据导出使用。 |
| 窗口聚焦 | `focus_window` | `focus_window(title_candidates)` | 真实 UI 执行前聚焦飞书窗口。 |

## 后端语义

- `DryRunDesktopBackend` 只记录 planned call，不触碰真实桌面，返回 `planned_only=true`。
- `PyAutoGuiBackend` 调用系统桌面能力执行真实动作，并把坐标、目标、动作结果写入 `BackendResult.metadata`。
- `MockActionExecutor` 面向安全回归，生成结构化 Action 和 trace，不执行桌面动作。

## 工程取舍

- 中文输入优先使用剪贴板粘贴，不逐字模拟输入法。
- 真实 UI 主链路禁止无证据固定坐标 fallback；定位失败应 `blocked` 并写入 trace。
- API 不执行 GUI 任务，只做 Oracle 验证。
- 双击、右键、拖拽、滚动已经具备 Backend 能力，但默认真实 smoke 仍只使用 IM 和 Docs 稳定链路需要的动作。
