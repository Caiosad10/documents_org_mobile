from __future__ import annotations

from datetime import date

from documents_org.models import Document, DocumentLink
from documents_org.services.rules import (
    calcular_status_mes,
    ids_vinculados,
    limpar_nome_arquivo,
    montar_vinculo_ids,
)


def doc(id_: str, type_: str = "comprovante", date_: str = "2026-05-10") -> Document:
    return Document(
        id=id_,
        user_id="user-1",
        date=date_,
        type=type_,
        file_path=f"user-1/{date_}/{id_}.pdf",
    )


def test_limpar_nome_arquivo_remove_caminho_e_caracteres_invalidos():
    assert limpar_nome_arquivo(r"C:\temp\boleto<>maio?.pdf") == "boleto_maio_.pdf"


def test_limpar_nome_arquivo_deixa_nome_seguro_para_storage():
    assert (
        limpar_nome_arquivo("PC_0101_MAT. ELÉT_CABO COBRE_SITE MSDOS-0950.pdf")
        == "PC_0101_MAT._ELET_CABO_COBRE_SITE_MSDOS-0950.pdf"
    )


def test_montar_vinculo_prioriza_comprovante():
    comprovante = doc("c1", "comprovante")
    nota = doc("n1", "nota_fiscal")

    assert montar_vinculo_ids(nota, comprovante) == ("c1", "n1")
    assert montar_vinculo_ids(comprovante, nota) == ("c1", "n1")


def test_montar_vinculo_entre_nao_comprovantes_usa_ordem_estavel():
    boleto = doc("b2", "boleto")
    recibo = doc("a1", "recibo")

    assert montar_vinculo_ids(boleto, recibo) == ("a1", "b2")


def test_ids_vinculados_encontra_dos_dois_lados():
    links = [
        DocumentLink(id="l1", comprovante_id="c1", documento_id="n1"),
        DocumentLink(id="l2", comprovante_id="c2", documento_id="c1"),
    ]

    assert ids_vinculados("c1", links) == {"n1", "c2"}


def test_calcular_status_empty_sem_documentos():
    status = calcular_status_mes([], [], 2026, 5, date(2026, 5, 20))

    assert status.status == "empty"
    assert status.dias_com_docs == 0
    assert status.pendencias == 0


def test_calcular_status_ok_quando_comprovantes_tem_link():
    docs = [doc("c1"), doc("n1", "nota_fiscal")]
    links = [DocumentLink(id="l1", comprovante_id="c1", documento_id="n1")]

    status = calcular_status_mes(docs, links, 2026, 5, date(2026, 5, 20))

    assert status.status == "ok"
    assert status.dias_com_docs == 1
    assert status.pendencias == 0


def test_calcular_status_pending_com_comprovante_sem_link():
    docs = [doc("c1"), doc("n1", "nota_fiscal")]

    status = calcular_status_mes(docs, [], 2026, 5, date(2026, 5, 20))

    assert status.status == "pending"
    assert status.pendencias == 1


def test_calcular_status_urgent_no_fim_do_mes_atual():
    docs = [doc("c1")]

    status = calcular_status_mes(docs, [], 2026, 5, date(2026, 5, 28))

    assert status.status == "urgent"
