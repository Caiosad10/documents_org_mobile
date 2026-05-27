from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from documents_org.config.constants import DEFAULT_BUCKET


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_key: str
    supabase_bucket: str = DEFAULT_BUCKET

    @property
    def auth_url(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    @property
    def rest_url(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/rest/v1"

    @property
    def storage_url(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/storage/v1"


def load_dotenv_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_settings(env_path: str | Path = ".env") -> Settings:
    load_dotenv_file(Path(env_path))

    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()
    bucket = os.getenv("SUPABASE_BUCKET", DEFAULT_BUCKET).strip() or DEFAULT_BUCKET

    missing = [name for name, value in {"SUPABASE_URL": url, "SUPABASE_KEY": key}.items() if not value]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(f"Configure {joined} no arquivo .env antes de entrar no app.")

    return Settings(supabase_url=url, supabase_key=key, supabase_bucket=bucket)

