# 引用来源与自研创新说明

本项目允许参考开源项目和论文思想，但当前代码没有把 UI-TARS、Touchpoint、OpenCLI、MCP、GUI-R1 或 ScaleCUA 作为运行时硬依赖。CUA-Lark 的主链路仍然是自研的视觉优先飞书桌面端测试框架。

最终演示和交付检查见 `docs/demo_script.md` 与 `docs/final_delivery_checklist.md`。

## 参考来源

| 来源 | 当前使用方式 |
| --- | --- |
| UI-TARS / UGround | 参考“视觉理解界面并输出 bbox / 坐标”的 GUI grounding 思路；未接入其模型、SDK 或桌面端执行框架。 |
| OSWorld | 参考真实计算机环境、任务级评测、可复现报告和成功率指标；落地为 FeishuWorld suite、`summary.json`、`summary.md` 和 `summary.html`。 |
| GUI-R1 | 参考“高质量 GUI 轨迹 + 可验证奖励”的数据路线；当前只导出 trace、few-shot 和 grounding eval，不训练模型。 |
| ScaleCUA | 参考跨任务轨迹数据标准化思想；当前只做飞书场景内的数据沉淀。 |
| ScenGen | 参考场景驱动、监督、记录和复盘思想；当前用状态机、Verifier、TraceRecorder 落地，不复刻多 Agent 架构。 |
| Touchpoint | 参考 Accessibility Tree 作为结构化候选增强定位；当前实现基于 Windows UI Automation 雏形，不依赖 Touchpoint。 |
| OpenCLI | 仅作为后置辅助方向，用于环境准备、状态读取、页面结构 dump 和 Electron/CDP 调试；不替代视觉 UI 操作。 |
| MCP | 当前只产出 local tool registry 和 MCP-ready manifest；未启动 MCP Server。 |

## 自研创新点

- **FeishuWorld 评测集**：把 IM / Docs 稳定真实链路和 mock 回归链路组织成 suite，统一输出指标和报告。
- **视觉优先执行闭环**：截图、OCR、VLM 摘要、混合定位、鼠标键盘操作、验证和 trace 全链路落盘。
- **HybridGrounder**：结合 VLM bbox、OCR 文本框和 Accessibility Tree 候选，记录 `coordinate_source`、bbox 和点击点。
- **分层 Verifier**：IM 使用截图证据、API oracle、OCR 和 VLM 组合验证；Docs 使用唯一标题后置验证阻断旧文档误判。
- **安全真实 UI 开关**：`--real-ui`、`--dry-run`、`--allow-send`、`--confirm-target` 分层放行，避免误操作真实环境。
- **Trace-first 数据沉淀**：每步保存 observation、action、verdict 和报告，可导出训练/评测友好的 JSONL。
- **MCP-ready 本地工具注册表**：先稳定工具 schema，再考虑 MCP Server，避免过早引入复杂运行时。

## 边界说明

- API 只做 Oracle 和状态验证，不直接代替桌面 UI 完成任务。
- 当前真实稳定能力以已验证的 IM 发测试群消息、Docs 创建指定标题云文档为准。
- Calendar、Cross-Product 等链路保留 mock / 叙事 / 失败分析价值，但不作为真实稳定能力扩写。
- 不宣称完成真实模型微调、强化学习或跨平台 ScaleCUA 数据规模化。
