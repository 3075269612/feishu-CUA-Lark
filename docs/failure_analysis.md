# 失败复盘

本文档记录真实 UI 验证中遇到的主要失败类型、修复策略和最终交付口径。它不是 README 的主叙事，而是工程复盘材料。

## 真实稳定口径

最终 `real-smoke` 只纳入两条稳定链路：

- IM：在飞书测试群 `CUA-Lark-Test` 中发送带 run_id 的消息。
- Docs：创建带唯一标题的云文档。

Calendar 和 Cross-Product 保留状态机、mock 评测、trace 和叙事价值，但不作为最终真实稳定 smoke 能力扩写。

## 失败类型与处理

### VLM 大 bbox 误点

现象：VLM 在 Docs 主页的 `STAGE_CLICK_NEW` 返回过大的 bbox，导致点击到页面推荐区域或无效区域。

处理：

- 对关键 Docs 阶段优先使用 OCR 精确匹配。
- `STAGE_CLICK_NEW` 只接受 `新建` 主标题和 `新建文档开始协作` 副标题组成的按钮。
- 找不到按钮时直接 `blocked`，不回退 VLM 乱点。

### OCR 漏识别

现象：IM 最新消息已经发出，API 和 VLM 可验证，但 OCR 可能漏掉完整 run_id 或把文本粘连。

处理：

- IM verifier 保留多源证据：截图、API Oracle、OCR、VLM。
- `visual_api_agreement` 用于衡量视觉证据和 API 证据是否一致。
- 报告保留各 verifier 的状态、原因和置信度，便于人工复核。

### Docs 旧标题误判

现象：旧文档列表中已有同名标题，可能让验证误以为新文档创建成功。

处理：

- Docs 创建标题加入 `{{run_id}}`，每次唯一。
- 创建后执行后置验证，要求当前页面像文档编辑器且能看到唯一标题。
- 旧列表页命中标题不再直接判 pass。

### 菜单状态不一致

现象：点击 `新建` 后，下拉菜单可能未出现或焦点变化，导致后续 `文档` / `新建空白文档` 查找失败。

处理：

- 状态机每步重新截图和 OCR。
- 如果菜单项缺失但仍能看到 `新建`，允许重新点击并不推进阶段。
- 每个 Docs 阶段设置尝试上限，超限后 `blocked` 并写入 trace。

### 窗口焦点和页面加载

现象：飞书或浏览器窗口切换、页面打开慢、输入区未聚焦，会导致后续粘贴或验证失败。

处理：

- 每条真实 UI run 先聚焦飞书窗口。
- 关键输入使用剪贴板粘贴，减少中文输入法不确定性。
- 后置验证基于截图、OCR、VLM 摘要和状态 marker，而不是只依赖动作返回。

## Failure Analysis 导出

Phase 8 可以把失败样本单独导出，用于后续复盘和 few-shot 负例设计：

```powershell
.\.conda310\python.exe -m cua_lark.main export-traces runs --out datasets\generated\failure_analysis --statuses blocked,fail,uncertain --max-runs 10
```

导出数据位于 `datasets/generated/`，默认不提交。

## 工程结论

- 真实 UI 的价值在于可验证闭环，而不是盲目扩产品覆盖。
- 对不稳定 UI 链路，应保留 trace、失败原因和 mock 回归，不应混入真实 smoke 成功率。
- 对外展示应强调 FeishuWorld 评测体系、分层验证、trace-first 和 Phase 8 数据沉淀。
