from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from urllib.parse import quote

import httpx

from documents_org.config.settings import Settings


@dataclass
class AuthState:
    user: Any | None = None
    session: Any | None = None

    @property
    def is_authenticated(self) -> bool:
        return self.user is not None and self.session is not None


class SupabaseGateway:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = httpx.Client(timeout=httpx.Timeout(connect=20, read=180, write=180, pool=20))
        self.state = AuthState()

    def sign_in(self, email: str, password: str) -> AuthState:
        response = self.client.post(
            f"{self.settings.auth_url}/token",
            params={"grant_type": "password"},
            headers=self._anon_headers(),
            json={"email": email, "password": password},
        )
        self._raise_for_status(response)
        data = response.json()
        user_data = data.get("user") or {}
        self.state = AuthState(
            user=SimpleNamespace(
                id=str(user_data.get("id", "")),
                email=str(user_data.get("email", email)),
            ),
            session=SimpleNamespace(
                access_token=str(data.get("access_token", "")),
                refresh_token=str(data.get("refresh_token", "")),
            ),
        )
        return self.state

    def sign_up(self, email: str, password: str) -> None:
        response = self.client.post(
            f"{self.settings.auth_url}/signup",
            headers=self._anon_headers(),
            json={"email": email, "password": password},
        )
        self._raise_for_status(response)

    def sign_out(self) -> None:
        self.state = AuthState()

    def rest_select(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        response = self.client.get(
            f"{self.settings.rest_url}/{table}",
            headers=self._auth_headers(),
            params=params,
        )
        self._raise_for_status(response)
        return response.json()

    def rest_insert(self, table: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        headers = self._auth_headers()
        headers["Prefer"] = "return=representation"
        response = self.client.post(
            f"{self.settings.rest_url}/{table}",
            headers=headers,
            json=payload,
        )
        self._raise_for_status(response)
        return response.json()

    def rest_delete(self, table: str, params: dict[str, str]) -> None:
        response = self.client.delete(
            f"{self.settings.rest_url}/{table}",
            headers=self._auth_headers(),
            params=params,
        )
        self._raise_for_status(response)

    def upload_object(self, path: str, content: bytes, content_type: str) -> None:
        response = self.client.post(
            f"{self.settings.storage_url}/object/{self.settings.supabase_bucket}/{path}",
            headers={
                **self._auth_headers(),
                "content-type": content_type,
            },
            content=content,
        )
        self._raise_for_status(response)

    def download_object(self, path: str) -> bytes:
        encoded_path = quote(path, safe="/")
        response = self.client.get(
            f"{self.settings.storage_url}/object/{self.settings.supabase_bucket}/{encoded_path}",
            headers=self._auth_headers(),
        )
        self._raise_for_status(response)
        return response.content

    def remove_objects(self, paths: list[str]) -> None:
        response = self.client.request(
            "DELETE",
            f"{self.settings.storage_url}/object/{self.settings.supabase_bucket}",
            headers=self._auth_headers(),
            json={"prefixes": paths},
        )
        self._raise_for_status(response)

    def _access_token(self) -> str:
        if not self.state.session:
            raise RuntimeError("Usuario nao autenticado.")
        return self.state.session.access_token

    def _anon_headers(self) -> dict[str, str]:
        return {
            "apikey": self.settings.supabase_key,
            "Authorization": f"Bearer {self.settings.supabase_key}",
            "content-type": "application/json",
        }

    def _auth_headers(self) -> dict[str, str]:
        return {
            "apikey": self.settings.supabase_key,
            "Authorization": f"Bearer {self._access_token()}",
        }

    def _raise_for_status(self, response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            raise RuntimeError(f"Erro Supabase {response.status_code}: {detail}") from exc
