from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Document:
    id: str
    user_id: str
    date: str
    type: str
    file_path: str
    tags: list[str] = field(default_factory=list)
    created_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Document":
        return cls(
            id=str(data.get("id", "")),
            user_id=str(data.get("user_id", "")),
            date=str(data.get("date", "")),
            type=str(data.get("type", "")),
            file_path=str(data.get("file_path", "")),
            tags=list(data.get("tags") or []),
            created_at=str(data.get("created_at", "")),
        )


@dataclass(frozen=True)
class DocumentLink:
    id: str
    comprovante_id: str
    documento_id: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DocumentLink":
        return cls(
            id=str(data.get("id", "")),
            comprovante_id=str(data.get("comprovante_id", "")),
            documento_id=str(data.get("documento_id", "")),
        )


@dataclass(frozen=True)
class MonthStatus:
    dias_com_docs: int
    pendencias: int
    status: str

