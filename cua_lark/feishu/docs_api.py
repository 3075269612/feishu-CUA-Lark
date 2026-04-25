from __future__ import annotations


class DocsApi:
    def doc_exists(self, title_contains: str) -> dict:
        return {"status": "disabled", "title_contains": title_contains}
