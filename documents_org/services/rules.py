from __future__ import annotations

import re
import uuid
from datetime import date
from typing import Iterable, Protocol

from documents_org.models import Document, DocumentLink, MonthStatus


class HasIdAndType(Protocol):
    id: str
    type: str


def limpar_nome_arquivo(nome: str) -> str:
    nome_limpo = nome.replace("\\", "/").split("/")[-1].strip()
    nome_limpo = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", nome_limpo)
    nome_limpo = re.sub(r"\s+", " ", nome_limpo)
    return nome_limpo or f"{uuid.uuid4()}.pdf"


def nome_documento(doc: Document) -> str:
    return doc.file_path.split("/")[-1]


def tipo_documento_label(tipo: str) -> str:
    return tipo.replace("_", " ").upper()


def montar_vinculo_ids(doc_origem: HasIdAndType, doc_destino: HasIdAndType) -> tuple[str, str]:
    if doc_origem.type == "comprovante":
        return doc_origem.id, doc_destino.id
    if doc_destino.type == "comprovante":
        return doc_destino.id, doc_origem.id

    ids = sorted([doc_origem.id, doc_destino.id])
    return ids[0], ids[1]


def ids_vinculados(doc_id: str, links: Iterable[DocumentLink]) -> set[str]:
    vinculados: set[str] = set()
    for link in links:
        if link.comprovante_id == doc_id:
            vinculados.add(link.documento_id)
        if link.documento_id == doc_id:
            vinculados.add(link.comprovante_id)
    return vinculados


def calcular_status_mes(
    docs: Iterable[Document],
    links: Iterable[DocumentLink],
    ano: int,
    mes: int,
    hoje: date | None = None,
) -> MonthStatus:
    hoje = hoje or date.today()
    docs_do_mes = [
        doc for doc in docs
        if doc.date.startswith(f"{ano}-{mes:02d}-")
    ]

    if not docs_do_mes:
        return MonthStatus(dias_com_docs=0, pendencias=0, status="empty")

    dias_com_docs = len({doc.date for doc in docs_do_mes})
    comprovantes = [doc for doc in docs_do_mes if doc.type == "comprovante"]
    ids_comprovantes = {doc.id for doc in comprovantes}
    comprovantes_com_link = {
        link.comprovante_id
        for link in links
        if link.comprovante_id in ids_comprovantes
    }
    pendencias = len(ids_comprovantes - comprovantes_com_link)

    if pendencias == 0:
        status = "ok" if ids_comprovantes else "empty"
    elif hoje.month == mes and hoje.year == ano and hoje.day >= 28:
        status = "urgent"
    else:
        status = "pending"

    return MonthStatus(dias_com_docs=dias_com_docs, pendencias=pendencias, status=status)

