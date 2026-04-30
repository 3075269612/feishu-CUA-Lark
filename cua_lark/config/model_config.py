from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


DEFAULT_SECRETS_PATH = Path("configs/secrets.local.yaml")


def load_local_secrets(path: str | Path = DEFAULT_SECRETS_PATH) -> dict[str, Any]:
    secrets_path = Path(path)
    if not secrets_path.exists():
        return {}
    with secrets_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data if isinstance(data, dict) else {}


@dataclass
class ModelConfig:
    provider: str = "mock"
    vlm_model: str = "mock-vlm"
    ocr_engine: str = "mock-ocr"
    temperature: float = 0.0
    timeout_sec: int = 30
    dashscope: dict[str, Any] = field(default_factory=dict)
    rapidocr: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str | Path = "configs/model.yaml") -> ModelConfig:
        with Path(path).open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        secrets = load_local_secrets()
        dashscope = {**(data.get("dashscope") or {}), **(secrets.get("dashscope") or {})}
        rapidocr = data.get("rapidocr") or {}
        return cls(
            provider=data.get("provider", "mock"),
            vlm_model=data.get("vlm_model", "mock-vlm"),
            ocr_engine=data.get("ocr_engine", "mock-ocr"),
            temperature=float(data.get("temperature", 0)),
            timeout_sec=int(data.get("timeout_sec", 30)),
            dashscope=dashscope,
            rapidocr=rapidocr,
        )

    @property
    def is_mock(self) -> bool:
        return self.provider == "mock"

    def dashscope_api_key(self) -> str | None:
        if self.dashscope.get("api_key"):
            return str(self.dashscope["api_key"])
        env_var = self.dashscope.get("api_key_env", "DASHSCOPE_API_KEY")
        return os.environ.get(env_var)
