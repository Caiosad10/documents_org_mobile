from __future__ import annotations

from types import SimpleNamespace

import flet as ft

from documents_org.models import Document, DocumentLink, MonthStatus
from main import DocumentsOrgFletApp


class FakePage:
    def __init__(self):
        self.controls = []
        self.overlay = []
        self.services = []
        self.dialog = None
        self.snack_bar = None

    def add(self, *controls):
        self.controls.extend(controls)

    def update(self):
        return None

    def show_dialog(self, dialog):
        dialog.open = True
        self.dialog = dialog

    def pop_dialog(self):
        dialog = self.dialog
        if dialog:
            dialog.open = False
        self.dialog = None
        return dialog


class FakeDocumentService:
    def obter_status_mes(self, ano: int, mes: int) -> MonthStatus:
        return MonthStatus(dias_com_docs=1 if mes == 5 else 0, pendencias=0, status="ok" if mes == 5 else "empty")

    def listar_dias_com_documentos(self, ano: int, mes: int) -> set[int]:
        return {10, 15}

    def listar_documentos_do_dia(self, data: str) -> list[Document]:
        return [
            Document(
                id="doc-1",
                user_id="user-1",
                date=data,
                type="comprovante",
                file_path=f"user-1/{data}/doc-1/comprovante.pdf",
                created_at=f"{data}T10:00:00",
            ),
            Document(
                id="doc-2",
                user_id="user-1",
                date=data,
                type="nota_fiscal",
                file_path=f"user-1/{data}/doc-2/nota.pdf",
                created_at=f"{data}T10:01:00",
            ),
        ]

    def listar_links_documentos(self, docs: list[Document]) -> list[DocumentLink]:
        return [DocumentLink(id="link-1", comprovante_id="doc-1", documento_id="doc-2")]

    def salvar_vinculo(self, source: Document, target: Document) -> bool:
        return True

    def desvincular_vinculo(self, link: DocumentLink) -> None:
        return None

    def excluir_documento(self, doc: Document) -> None:
        return None


def make_app() -> DocumentsOrgFletApp:
    app = DocumentsOrgFletApp(FakePage())
    app.gateway.state.user = SimpleNamespace(email="user@example.com", id="user-1")
    app.documents = FakeDocumentService()
    return app


def test_show_auth_builds_without_flet_api_errors():
    app = make_app()

    app.show_auth()

    assert app.page.controls
    assert not app.page.overlay
    assert any(isinstance(service, ft.FilePicker) for service in app.page.services)


def test_loading_overlay_can_open_and_close():
    app = make_app()

    app.show_loading("Testando...")
    assert app.page.overlay

    app.hide_loading()
    assert not app.page.overlay


def test_header_and_month_card_build_without_flet_api_errors():
    app = make_app()

    header = app.header("Titulo", "Subtitulo")
    month = app.month_card(2026, 5, MonthStatus(dias_com_docs=1, pendencias=0, status="ok"))

    assert isinstance(header, ft.Container)
    assert isinstance(month, ft.Container)


def test_dashboard_builds_month_cards_without_flet_api_errors():
    app = make_app()

    app.show_dashboard()

    assert app.page.controls


def test_calendar_builds_grid_without_flet_api_errors():
    app = make_app()
    app.selected_month = 5

    app.show_calendar()

    assert app.page.controls


def test_day_screen_builds_upload_and_document_cards_without_flet_api_errors():
    app = make_app()
    app.selected_month = 5
    app.selected_day = 10

    app.show_day()

    assert app.page.controls


def test_day_screen_handles_multiple_selected_files_label():
    app = make_app()
    app.selected_month = 5
    app.selected_day = 10
    app.selected_files = ["C:/tmp/a.pdf", "C:/tmp/b.pdf"]

    assert app.selected_file_name() == "2 arquivos selecionados"


def test_link_and_delete_dialogs_build_without_flet_api_errors():
    app = make_app()
    app.selected_month = 5
    app.selected_day = 10
    docs = app.documents.listar_documentos_do_dia(app.data_str)
    links = []

    app.open_link_dialog(docs[0], docs, links)
    assert isinstance(app.page.dialog, ft.AlertDialog)

    app.confirm_delete(docs[0])
    assert isinstance(app.page.dialog, ft.AlertDialog)
