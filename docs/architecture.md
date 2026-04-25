# Architecture

CUA-Lark follows a seven-module architecture for visual-first desktop testing.

1. TaskSpec turns natural-language test intent and YAML slots into a controlled executable spec.
2. Planner reads the task and Feishu skill notes, then emits small step goals instead of one long brittle click script.
3. Perceptor captures screenshots and later enriches them with VLM summaries, OCR text, and Accessibility candidates.
4. Grounder maps a goal such as "click the message input" to coordinates using visual bbox first, with OCR and Accessibility as assists.
5. Actor executes desktop operations. Phase 1 only returns mock actions.
6. Verifier checks whether each step and final task succeeded through visual, OCR, structural, and API evidence.
7. Trace/Report records every observation, action, verdict, recovery, and final report for replay and audit.

## Principles

- Visual first: the main operation path must be screenshot/VLM driven.
- Structure assisted: OCR, Accessibility Tree, and future Touchpoint data improve localization and verification, but do not replace visual decisions.
- API oracle: Feishu OpenAPI is for test data setup and final-state verification, not for directly completing UI tasks.

Phase 0/1 keeps all real integrations behind importable stubs so the project can run safely while the interfaces stabilize.
