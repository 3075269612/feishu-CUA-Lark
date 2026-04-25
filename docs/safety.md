# Safety

CUA-Lark must only operate in a prepared test environment.

## Allowlist Strategy

The safety config controls:

- allowed chats
- allowed contacts
- allowed doc folders
- allowed calendar keywords
- forbidden actions

The guard blocks tasks or actions whose targets are outside the allowlist. Calendar items must include an allowed keyword such as `CUA-Lark`.

## Real Environment Protection

The agent must not message external contacts, invite external users, share public links, delete real docs, or mass send. These forbidden actions are blocked before execution.

## Tokens And Screenshots

API tokens belong in `.env`, never in git. Screenshots and traces may contain private information, so `runs/` is ignored by default. Only sanitized artifacts should be shared.

## API Boundary

Feishu OpenAPI can prepare data or verify final state. It must not replace desktop UI operations in the main test path.
