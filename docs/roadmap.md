# Roadmap

## Phase 0: Environment And Safety Boundaries

Prepare test tenant, test accounts, test group `CUA-Lark-Test`, test contacts, doc folders, calendar naming rules, desktop resolution, login state, secrets, and allowlists.

## Phase 1: Atomic Operations And Mock Loop

Build task loading, safety checks, mock planning, mock action execution, trace recording, and Markdown reports.

## Phase 2: IM Send Message Loop

Drive the real desktop UI to search the test group, send text, verify visually, and optionally verify by Feishu OpenAPI.

## Phase 3: Hybrid Grounding

Combine VLM bbox, OCR text boxes, and Accessibility candidates. Prefer visual grounding, then snap to structural candidates when confidence is high.

## Phase 4: Calendar

Create, modify, and delete test calendar events whose titles include allowed CUA-Lark keywords.

## Phase 5: Docs

Create test documents, edit title/body content, and verify metadata/content without touching real folders.

## Phase 6: Cross Product Chain

Connect IM, Calendar, Docs, and IM summary steps using explicit subtask state instead of free-form agent behavior.

## Phase 7: Evaluation Set And Reports

Run a small FeishuWorld suite, measure success rate, step count, duration, recovery count, and visual/API agreement.
