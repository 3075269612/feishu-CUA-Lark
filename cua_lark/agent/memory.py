from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Memory:
    values: dict[str, Any] = field(default_factory=dict)

    def update(self, values: dict[str, Any]) -> None:
        self.values.update(values)
