from __future__ import annotations

import calendar
import mimetypes
import uuid
from datetime import date
from pathlib import Path

from documents_org.models import Document, DocumentLink, MonthStatus
from documents_org.services.rules import (
    calcular_status_mes,
    limpar_nome_arquivo,
    montar_vinculo_ids,
)
from documents_org.services.supabase_client import SupabaseGateway


class DocumentService:
    def __init__(self, gateway: SupabaseGateway):
        self.gateway = gateway

    @property
    def user_id(self) -> str:
        user = self.gateway.state.user
        if not user:
            raise RuntimeError("Usuario nao autenticado.")
        return str(user.id)

    def obter_status_mes(self, ano: int, mes: int) -> MonthStatus:
        inicio = f"{ano}-{mes:02d}-01"
        ultimo_dia = calendar.monthrange(ano, mes)[1]
        fim = f"{ano}-{mes:02d}-{ultimo_dia}"

        data = self.gateway.rest_select(
            "documents",
            {
                "select": "id,user_id,date,type,file_path,tags,created_at",
                "and": f"(date.gte.{inicio},date.lte.{fim})",
            },
        )
        docs = [Document.from_dict(item) for item in data]
        ids_comprovantes = [doc.id for doc in docs if doc.type == "comprovante"]
        links = self._links_por_comprovantes(ids_comprovantes)
        return calcular_status_mes(docs, links, ano, mes, date.today())

    def listar_dias_com_documentos(self, ano: int, mes: int) -> set[int]:
        inicio = f"{ano}-{mes:02d}-01"
        ultimo_dia = calendar.monthrange(ano, mes)[1]
        fim = f"{ano}-{mes:02d}-{ultimo_dia}"
        data = self.gateway.rest_select(
            "documents",
            {
                "select": "date",
                "and": f"(date.gte.{inicio},date.lte.{fim})",
            },
        )
        return {int(item["date"].split("-")[2]) for item in data}

    def listar_documentos_do_dia(self, data: str) -> list[Document]:
        rows = self.gateway.rest_select(
            "documents",
            {
                "select": "*",
                "date": f"eq.{data}",
                "order": "created_at.asc",
            },
        )
        return [Document.from_dict(item) for item in rows]

    def listar_links_documentos(self, docs: list[Document]) -> list[DocumentLink]:
        if not docs:
            return []

        ids = [doc.id for doc in docs]
        links: dict[str, DocumentLink] = {}
        ids_filter = ",".join(ids)
        por_comprovante = self.gateway.rest_select(
            "links",
            {
                "select": "*",
                "comprovante_id": f"in.({ids_filter})",
            },
        )
        por_documento = self.gateway.rest_select(
            "links",
            {
                "select": "*",
                "documento_id": f"in.({ids_filter})",
            },
        )

        for item in por_comprovante + por_documento:
            link = DocumentLink.from_dict(item)
            links[link.id] = link
        return list(links.values())

    def salvar_documento_do_arquivo(self, arquivo_local: str | Path, data: str, tipo: str) -> Document:
        file_path = self.fazer_upload(arquivo_local, data)
        rows = self.gateway.rest_insert(
            "documents",
            {
                "user_id": self.user_id,
                "date": data,
                "type": tipo,
                "file_path": file_path,
                "tags": [],
            },
        )
        return Document.from_dict((rows or [{}])[0])

    def fazer_upload(self, arquivo_local: str | Path, data: str) -> str:
        path = Path(arquivo_local)
        nome_arquivo = limpar_nome_arquivo(path.name)
        pasta_unica = str(uuid.uuid4())
        destino = f"{self.user_id}/{data}/{pasta_unica}/{nome_arquivo}"
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"

        self.gateway.upload_object(destino, path.read_bytes(), content_type)
        return destino

    def salvar_vinculo(self, doc_origem: Document, doc_destino: Document) -> bool:
        comprovante_id, documento_id = montar_vinculo_ids(doc_origem, doc_destino)
        if comprovante_id == documento_id:
            return False

        existente = self.gateway.rest_select(
            "links",
            {
                "select": "id",
                "comprovante_id": f"eq.{comprovante_id}",
                "documento_id": f"eq.{documento_id}",
            },
        )
        if existente:
            return False

        self.gateway.rest_insert("links", {"comprovante_id": comprovante_id, "documento_id": documento_id})
        return True

    def desvincular_vinculo(self, link: DocumentLink) -> None:
        self.gateway.rest_delete("links", {"id": f"eq.{link.id}"})

    def excluir_documento(self, doc: Document) -> None:
        self.gateway.rest_delete("links", {"comprovante_id": f"eq.{doc.id}"})
        self.gateway.rest_delete("links", {"documento_id": f"eq.{doc.id}"})
        self.gateway.rest_delete("documents", {"id": f"eq.{doc.id}"})

        try:
            self.gateway.remove_objects([doc.file_path])
        except Exception:
            pass

    def _links_por_comprovantes(self, comprovante_ids: list[str]) -> list[DocumentLink]:
        if not comprovante_ids:
            return []
        ids_filter = ",".join(comprovante_ids)
        rows = self.gateway.rest_select(
            "links",
            {
                "select": "*",
                "comprovante_id": f"in.({ids_filter})",
            },
        )
        return [DocumentLink.from_dict(item) for item in rows]
