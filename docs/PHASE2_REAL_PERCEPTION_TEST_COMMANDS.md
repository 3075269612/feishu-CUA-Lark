# Phase 2 Real Perception Test Commands

Last updated: 2026-04-30

This branch uses hybrid grounding for real UI runs:

```text
screenshot -> OCR -> Accessibility Tree -> VLM bbox -> HybridGrounder -> UI action
```

The real UI send flow must not use fixed-coordinate anchors.

## Full Automated Test Suite

```powershell
.\.conda310\python.exe -m pytest tests
```

Expected result:

```text
78 passed
```

## Real UI Send Test

This command controls the local Feishu/Lark desktop client and sends a real message to `CUA-Lark-Test`.

```powershell
.\.conda310\python.exe -m cua_lark.main run testcases/im/send_text.yaml --real-ui --confirm-target CUA-Lark-Test --allow-send --strict-verification --grounding hybrid 2>&1
```

Expected result:

```text
Status: pass
```

The report should show:

```text
grounding: hybrid
api_oracle: pass
ocr: pass
vlm: pass
```

It should not contain:

```text
coordinate_plan
config_fixed_anchor
```

Latest validation on 2026-04-30:

```text
Command: .\.conda310\python.exe -m cua_lark.main run testcases/im/send_text.yaml --real-ui --confirm-target CUA-Lark-Test --allow-send --strict-verification --grounding hybrid --runs-dir .pytest_tmp_validate 2>&1
Run ID: 20260430_191554_357619
Status: pass
api_oracle: pass
ocr: pass
vlm: pass
```

## Real UI Dry Run

Use this before sending if you want to validate the control path without sending a message.

```powershell
.\.conda310\python.exe -m cua_lark.main run testcases/im/send_text.yaml --real-ui --confirm-target CUA-Lark-Test --dry-run --grounding hybrid 2>&1
```

Expected result:

```text
Status: uncertain
```

## Mock Test

```powershell
.\.conda310\python.exe -m cua_lark.main run testcases/im/send_text.yaml --mock 2>&1
```

Expected result:

```text
Status: pass
```

## Credentials

Secrets are read from `configs/secrets.local.yaml` and must not be committed.

Required shape:

```yaml
dashscope:
  api_key: "..."

feishu:
  app_id: "..."
  app_secret: "..."
  api_base_url: "https://open.feishu.cn/open-apis"
```

The verifier uses these paths:

```text
VLM: ModelConfig -> configs/model.yaml -> configs/secrets.local.yaml
Feishu API: ImApi -> FeishuAuth -> configs/secrets.local.yaml
```

## Cleanup Command

Keep generated-output directories but clear their contents:

```powershell
$dirsToClear = @('runs', '.pytest_tmp_manual', '.pytest_tmp_root', '.pytest_tmp_validate', 'cua_lark.egg-info', '__pycache__')
foreach ($rel in $dirsToClear) {
  if (-not (Test-Path -LiteralPath $rel)) { New-Item -ItemType Directory -Path $rel | Out-Null }
  Get-ChildItem -LiteralPath $rel -Force | ForEach-Object {
    Remove-Item -LiteralPath $_.FullName -Recurse -Force
  }
}
```
