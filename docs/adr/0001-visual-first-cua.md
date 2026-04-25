# ADR 0001: Visual-First CUA

## Status

Accepted.

## Context

The competition asks for an agent that can understand and operate the Feishu desktop client like a user. Traditional API or selector-based automation is useful but fragile against desktop UI changes and does not demonstrate the core CUA capability.

## Decision

CUA-Lark will make screenshots and visual reasoning the primary execution path. OCR, Accessibility Tree, Touchpoint-like structural data, and Feishu OpenAPI are supporting signals.

## Consequences

- The project starts with trace and verification infrastructure before real model integration.
- Feishu OpenAPI is reserved for setup and oracle checks.
- OpenCLI or MCP can be introduced later as auxiliary tooling, not as the main path.
