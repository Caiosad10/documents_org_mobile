from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import flet as ft

from documents_org.models import Document, DocumentLink, MonthStatus
import main as main_module
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
    def __init__(self):
        self.deleted: list[str] = []

    def obter_status_mes(self, ano: int, mes: int) -> MonthStatus:
        return MonthStatus(dias_com_docs=1 if mes == 5 else 0, pendencias=0, status="ok" if mes == 5 else "empty")

    def listar_dias_com_documentos(self, ano: int, mes: int) -> set[int]:
        return {10, 15}

    def listar_documentos_do_mes(self, ano: int, mes: int) -> list[Document]:
        return self.listar_documentos_do_dia(f"{ano}-{mes:02d}-10") + [
            Document(
                id="doc-3",
                user_id="user-1",
                date=f"{ano}-{mes:02d}-15",
                type="comprovante",
                file_path=f"user-1/{ano}-{mes:02d}-15/doc-3/pendente.pdf",
                created_at=f"{ano}-{mes:02d}-15T10:00:00",
            )
        ]

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

    def baixar_documento(self, doc: Document) -> bytes:
        if doc.file_path.lower().endswith(".pdf"):
            return b"%PDF-1.4\n%fake"
        return b"fake"

    def salvar_vinculo(self, source: Document, target: Document) -> bool:
        return True

    def desvincular_vinculo(self, link: DocumentLink) -> None:
        return None

    def excluir_documento(self, doc: Document) -> None:
        self.deleted.append(doc.id)
        return None


def make_app() -> DocumentsOrgFletApp:
    app = DocumentsOrgFletApp(FakePage())
    app.gateway.state.user = SimpleNamespace(email="user@example.com", id="user-1")
    app.documents = FakeDocumentService()
    return app


def output_dir_for_test(name: str) -> Path:
    return Path(".test_exports") / f"{name}_{uuid4().hex}"


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


def test_month_closing_builds_without_flet_api_errors():
    app = make_app()
    app.selected_month = 5

    app.show_month_closing()

    assert app.page.controls


def test_month_closing_html_export_creates_printable_file():
    app = make_app()
    docs = app.documents.listar_documentos_do_mes(2026, 5)
    links = app.documents.listar_links_documentos(docs)
    output_dir = output_dir_for_test("html_export")

    path = app.export_month_closing_html(2026, 5, docs, links, output_dir=output_dir)
    content = path.read_text(encoding="utf-8")

    assert path.exists()
    assert "Documentos para impressao - Maio 2026" in content
    assert "window.print()" in content
    assert "Arquivos reais ordenados por dia" in content
    assert "document-frame" in content
    assert "comprovante.pdf" in content
    assert (output_dir / "fechamento_2026_05_arquivos").exists()


def test_month_print_files_follow_linked_order():
    app = make_app()
    docs = app.documents.listar_documentos_do_mes(2026, 5)
    links = app.documents.listar_links_documentos(docs)
    output_dir = output_dir_for_test("print_files")

    ordered_docs, document_paths, _assets_dir = app.prepare_month_print_files(2026, 5, docs, links, output_dir=output_dir)
    names = [document_paths[doc.id].name for doc in ordered_docs]

    assert names == [
        "001_2026-05-10_comprovante.pdf",
        "002_2026-05-10_nota.pdf",
        "003_2026-05-15_pendente.pdf",
    ]


def test_automatic_print_uses_queue_and_cleans_temp(monkeypatch):
    app = make_app()
    docs = app.documents.listar_documentos_do_mes(2026, 5)
    links = app.documents.listar_links_documentos(docs)
    output_dir = output_dir_for_test("print_queue")
    printed: list[str] = []
    cleaned: list[Path] = []

    app.print_local_file = lambda path: printed.append(path.name)
    app.clean_print_assets_dir = lambda path: cleaned.append(path)
    monkeypatch.setattr(main_module.time, "sleep", lambda _seconds: None)

    count = app.print_month_closing_documents(2026, 5, docs, links, output_dir=output_dir)

    assert count == 3
    assert printed == [
        "001_2026-05-10_comprovante.pdf",
        "002_2026-05-10_nota.pdf",
        "003_2026-05-15_pendente.pdf",
    ]
    assert cleaned == [output_dir / "fechamento_2026_05_arquivos"]


def test_day_screen_builds_upload_and_document_cards_without_flet_api_errors():
    app = make_app()
    app.selected_month = 5
    app.selected_day = 10

    app.show_day()

    assert app.page.controls


def test_bulk_delete_selection_helpers():
    app = make_app()
    app.selected_month = 5
    app.selected_day = 10
    docs = app.documents.listar_documentos_do_dia(app.data_str)

    app.select_all_documents(docs)
    assert app.selected_delete_ids == {"doc-1", "doc-2"}

    app.clear_delete_selection()
    assert app.selected_delete_ids == set()

    app.toggle_delete_selection("doc-1", True)
    assert app.selected_delete_ids == {"doc-1"}

    app.prune_delete_selection([docs[1]])
    assert app.selected_delete_ids == set()


def test_bulk_delete_dialog_builds_for_selected_documents():
    app = make_app()
    app.selected_month = 5
    app.selected_day = 10
    docs = app.documents.listar_documentos_do_dia(app.data_str)
    app.selected_delete_ids = {"doc-1", "doc-2"}

    app.confirm_delete_selected(docs)

    assert isinstance(app.page.dialog, ft.AlertDialog)


def test_day_screen_handles_multiple_selected_files_label():
    app = make_app()
    app.selected_month = 5
    app.selected_day = 10
    app.selected_files = ["C:/tmp/a.pdf", "C:/tmp/b.pdf"]

    assert app.selected_file_name() == "2 arquivos selecionados"


def test_remove_upload_item_updates_selection():
    app = make_app()
    app.selected_month = 5
    app.selected_day = 10
    app.selected_upload_items = [
        {"key": "selected-0", "path": "C:/tmp/a.pdf", "type": "PC", "link_target": "selected-1"},
        {"key": "selected-1", "path": "C:/tmp/b.pdf", "type": "comprovante", "link_target": "none"},
    ]
    app.selected_files = [item["path"] for item in app.selected_upload_items]

    app.remove_upload_item(0)

    assert app.selected_files == ["C:/tmp/b.pdf"]
    assert app.selected_upload_items == [{"key": "selected-1", "path": "C:/tmp/b.pdf", "type": "comprovante", "link_target": "none"}]


def test_upload_item_can_target_another_selected_file():
    app = make_app()
    app.selected_upload_items = [
        {"key": "selected-0", "path": "C:/tmp/a.pdf", "type": "PC", "link_target": "none"},
        {"key": "selected-1", "path": "C:/tmp/b.pdf", "type": "comprovante", "link_target": "none"},
    ]

    app.update_upload_item_link_target(0, "selected-1")

    assert app.selected_upload_items[0]["link_target"] == "selected-1"


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
