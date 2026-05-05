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

实现可插拔 IM verifier chain：截图证据、任务验收项、optional API oracle、OCR/VLM placeholder。未配置 token 或未启用模型时 verifier 返回 skipped，不报错。

状态：已实现验证骨架和报告。只有 API/OCR/VLM 等自动 verifier 明确通过时才给自动 pass；仅截图证据通过时给 `needs_manual_verification`。

## Phase 3：混合定位

组合 VLM bbox、OCR 文本框和 Accessibility 候选。视觉定位优先，结构候选只用于坐标吸附和稳定性提升。

状态：已基本实现，当前 `feat/phase3-hybrid-grounding` 分支用于收口验证。

已实现：

- 真实 UI 观测链路保存截图并提取 OCR 文本与 Accessibility Tree 候选。
- `HybridGrounder` 先使用 VLM bbox，再用 Accessibility / OCR 候选做 IoU 与语义匹配吸附。
- 定位 metadata 记录 `coordinate_source`、`raw_vlm_bbox`、`calibrated_vlm_bbox`、`final_bbox` 和 `screenshot_point`。
- 消息入口和会话列表定位失败时阻断，不回退到固定坐标；飞书 OpenAPI 仍只作为验证 Oracle。

收口验证：

- 单测覆盖 VLM、OCR、Accessibility 吸附和无固定坐标 fallback。
- 真实 UI 发送验证命令保留在 `docs/PHASE2_REAL_PERCEPTION_TEST_COMMANDS.md`，默认不自动执行真实发送。

## Phase 4：Calendar

创建、修改、删除测试日程，标题必须包含 CUA-Lark allowlist 关键词。

## Phase 5：Docs

**状态：已完成。**

### 创建空白文档（create_blank_doc）

通过纯 GUI 点击链路创建飞书空白文档：
1. 点击左侧栏"云文档"入口
2. 点击"新建"按钮
3. 选择"文档"类型
4. 点击"新建空白文档"
5. 浏览器自动打开，在标题输入区填入标题

所有点击使用 VLM + OCR + Accessibility Tree 混合定位。标题输入使用比例坐标（35%/18%）定位输入区。已通过真实飞书桌面端验证。

### 编辑已有文档（edit_doc）

采用"强键盘、弱鼠标（Keyboard-Driven, Mouse-Assisted）"策略规避 VLM 在密集文本区的坐标漂移：
1. Ctrl+K 搜索目标文档
2. 粘贴文档名
3. 点击进入文档
4. 点击正文中央激活焦点
5. Ctrl+F → 粘贴锚点文本 → Enter → Esc → 方向键微调 → 粘贴最终内容

Stage 4 强制禁止鼠标点击正文区域（y_ratio > 0.15 即拦截），确保全键盘定位。已通过真实飞书桌面端验证。

## Phase 6：跨产品链路

用显式子任务状态机连接 IM、Calendar、Docs 和 IM 汇总，不允许让模型自由长链路操作。

## Phase 7：评测集与报告

构建 FeishuWorld 小型评测集，统计成功率、平均步数、耗时、恢复次数、失败分类和视觉/API 一致性。
