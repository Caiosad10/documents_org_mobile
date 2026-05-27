from __future__ import annotations

import asyncio
import calendar
import os
from datetime import date
from pathlib import Path

import flet as ft

from documents_org.config.constants import DIAS_SEMANA, MESES_PT, TIPOS_DOCUMENTO
from documents_org.config.settings import load_settings
from documents_org.models import Document
from documents_org.services.document_service import DocumentService
from documents_org.services.rules import ids_vinculados, nome_documento, tipo_documento_label
from documents_org.services.supabase_client import SupabaseGateway


BG = "#020617"
PANEL = "#0f1f3d"
PANEL_ALT = "#07111f"
LINE = "#1d4ed8"
TEXT = "#f1f5f9"
MUTED = "#94a3b8"
BLUE = "#3b82f6"
GREEN = "#86efac"
YELLOW = "#fde047"
RED = "#fca5a5"
CENTER = ft.alignment.Alignment(0, 0)


def pad(horizontal: int = 0, vertical: int = 0) -> ft.padding.Padding:
    return ft.padding.Padding(
        left=horizontal,
        right=horizontal,
        top=vertical,
        bottom=vertical,
    )


def border_all(width: int | float, color: str) -> ft.border.Border:
    side = ft.border.BorderSide(width=width, color=color)
    return ft.border.Border(top=side, right=side, bottom=side, left=side)


class DocumentsOrgFletApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Organizador de Documentos"
        self.page.bgcolor = BG
        self.page.padding = 0
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.window_width = 420
        self.page.window_height = 820
        self.page.scroll = ft.ScrollMode.AUTO

        self.gateway = SupabaseGateway(load_settings(Path(__file__).with_name(".env")))
        self.documents = DocumentService(self.gateway)
        self.selected_month: int | None = None
        self.selected_day: int | None = None
        self.selected_files: list[str] = []
        self.selected_upload_items: list[dict[str, str]] = []
        self.selected_upload_type = TIPOS_DOCUMENTO[0]
        self.selected_link_target_id = "none"
        self.current_dialog = None
        self.loading_overlay = None
        self.file_picker = ft.FilePicker()
        self.page.services.append(self.file_picker)

    def run(self) -> None:
        self.show_auth()

    def shell(self, controls: list[ft.Control]) -> None:
        self.page.controls.clear()
        self.page.add(
            ft.Container(
                expand=True,
                bgcolor=BG,
                padding=pad(horizontal=18, vertical=22),
                content=ft.Column(controls=controls, spacing=14, expand=True, scroll=ft.ScrollMode.AUTO),
            )
        )
        self.page.update()

    def toast(self, message: str, color: str = PANEL) -> None:
        self.show_dialog(ft.SnackBar(ft.Text(message), bgcolor=color))

    def show_loading(self, message: str = "Carregando...") -> None:
        self.hide_loading(update=False)
        self.loading_overlay = ft.Container(
            expand=True,
            bgcolor="#99000000",
            alignment=CENTER,
            content=ft.Container(
                width=260,
                padding=22,
                bgcolor=PANEL,
                border=border_all(1, "#1e3a8a"),
                border_radius=18,
                content=ft.Column(
                    [
                        ft.ProgressRing(color=BLUE, stroke_width=4),
                        ft.Text(message, color=TEXT, size=14, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                    ],
                    spacing=14,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    tight=True,
                ),
            ),
        )
        self.page.overlay.append(self.loading_overlay)
        self.page.update()

    def hide_loading(self, update: bool = True) -> None:
        if self.loading_overlay and self.loading_overlay in self.page.overlay:
            self.page.overlay.remove(self.loading_overlay)
        self.loading_overlay = None
        if update:
            self.page.update()

    async def with_loading(self, message: str, action):
        self.show_loading(message)
        await asyncio.sleep(0.05)
        try:
            return action()
        finally:
            self.hide_loading()

    def show_dialog(self, dialog: ft.DialogControl) -> None:
        self.current_dialog = dialog
        if hasattr(self.page, "show_dialog"):
            self.page.show_dialog(dialog)
        else:
            dialog.open = True
            self.page.dialog = dialog
            self.page.update()

    def close_dialog(self) -> None:
        if hasattr(self.page, "pop_dialog"):
            self.page.pop_dialog()
        elif self.current_dialog:
            self.current_dialog.open = False
            self.page.update()
        self.current_dialog = None

    def card(self, content: ft.Control, padding=16) -> ft.Container:
        return ft.Container(
            content=content,
            padding=padding,
            bgcolor=PANEL,
            border=border_all(1, "#1e3a8a"),
            border_radius=18,
            shadow=ft.BoxShadow(blur_radius=22, color="#00000066", offset=ft.Offset(0, 10)),
        )

    def title(self, text: str, size=22) -> ft.Text:
        return ft.Text(text, size=size, weight=ft.FontWeight.BOLD, color=TEXT)

    def subtitle(self, text: str) -> ft.Text:
        return ft.Text(text, size=13, color=MUTED)

    def button(self, text: str, handler, primary=False) -> ft.Control:
        style = ft.ButtonStyle(
            bgcolor=BLUE if primary else "#10254a",
            color=TEXT,
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=pad(horizontal=14, vertical=12),
        )
        return ft.Button(text, on_click=handler, style=style)

    def show_auth(self) -> None:
        email = ft.TextField(label="Email", value=os.getenv("DEV_AUTH_EMAIL", ""), border_radius=12, bgcolor=PANEL_ALT)
        password = ft.TextField(
            label="Senha",
            value=os.getenv("DEV_AUTH_PASSWORD", ""),
            password=True,
            can_reveal_password=True,
            border_radius=12,
            bgcolor=PANEL_ALT,
        )
        status = ft.Text("", color=YELLOW, size=12)

        async def login(_):
            if not email.value or not password.value:
                status.value = "Preencha email e senha."
                self.page.update()
                return
            status.value = "Entrando..."
            self.page.update()
            try:
                def action():
                    self.gateway.sign_in(email.value.strip(), password.value)
                    self.show_dashboard()

                await self.with_loading("Entrando...", action)
            except Exception as exc:
                status.value = "Nao foi possivel entrar."
                self.toast(str(exc), RED)

        async def signup(_):
            if not email.value or not password.value:
                status.value = "Preencha email e senha."
                self.page.update()
                return
            status.value = "Criando conta..."
            self.page.update()
            try:
                await self.with_loading(
                    "Criando conta...",
                    lambda: self.gateway.sign_up(email.value.strip(), password.value),
                )
                status.value = "Conta criada. Entre para continuar."
            except Exception as exc:
                status.value = "Nao foi possivel criar a conta."
                self.toast(str(exc), RED)
            self.page.update()

        form = self.card(
            ft.Column(
                [
                    self.title("Organizador de Documentos", 24),
                    self.subtitle("Acesse seu painel financeiro."),
                    email,
                    password,
                    self.button("Entrar", login, primary=True),
                    self.button("Criar conta", signup),
                    status,
                ],
                spacing=14,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            padding=22,
        )
        self.shell([ft.Container(height=80), form])

    def header(self, title: str, subtitle: str, include_logout=True) -> ft.Control:
        controls: list[ft.Control] = [
            ft.Row(
                [
                    ft.Column([self.title(title), self.subtitle(subtitle)], expand=True, spacing=2),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
        ]
        if include_logout:
            user = self.gateway.state.user
            controls.append(
                ft.Row(
                    [
                        ft.Text(getattr(user, "email", ""), color=MUTED, size=12, expand=True),
                        self.button("Sair", lambda _: self.logout()),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                )
            )
        return self.card(ft.Column(controls, spacing=10))

    def logout(self) -> None:
        self.gateway.sign_out()
        self.selected_month = None
        self.selected_day = None
        self.show_auth()

    def show_dashboard(self) -> None:
        year = date.today().year
        loading = ft.Text("Carregando meses...", color=MUTED)
        self.shell([self.header("Seu ano em documentos", "Escolha um mes para organizar seus arquivos."), loading])

        try:
            cards = []
            for month in range(1, 13):
                status = self.documents.obter_status_mes(year, month)
                cards.append(self.month_card(year, month, status))
            self.shell([self.header("Seu ano em documentos", "Escolha um mes para organizar seus arquivos."), *cards])
        except Exception as exc:
            self.toast(str(exc), RED)
            loading.value = "Nao foi possivel carregar os meses."
            self.page.update()

    def month_card(self, year: int, month: int, status) -> ft.Control:
        status_color = {
            "ok": GREEN,
            "pending": YELLOW,
            "urgent": RED,
            "empty": MUTED,
        }.get(status.status, MUTED)
        status_text = {
            "ok": "Tudo em dia",
            "pending": "Pendencias",
            "urgent": "Urgente",
            "empty": "Sem documentos",
        }.get(status.status, "Sem documentos")

        async def open_month(_):
            self.selected_month = month
            self.selected_day = None
            await self.with_loading("Abrindo calendario...", self.show_calendar)

        return self.card(
            ft.Column(
                [
                    ft.Text(str(year), color=MUTED, size=11),
                    self.title(MESES_PT[month - 1], 18),
                    ft.Text(f"{status.dias_com_docs} dias com documentos", color=MUTED, size=12),
                    ft.Text(f"{status.pendencias} pendencia(s)", color=MUTED, size=12),
                    ft.Text(status_text, color=status_color, size=12, weight=ft.FontWeight.BOLD),
                    self.button("Abrir", open_month),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            )
        )

    def show_calendar(self) -> None:
        if not self.selected_month:
            self.show_dashboard()
            return
        year = date.today().year
        month = self.selected_month
        header = self.header(f"{MESES_PT[month - 1]} {year}", "Selecione um dia para gerenciar os documentos.", False)
        try:
            days_with_docs = self.documents.listar_dias_com_documentos(year, month)
        except Exception as exc:
            days_with_docs = set()
            self.toast(str(exc), RED)

        def day_cell(day: int, has_docs: bool) -> ft.Container:
            controls: list[ft.Control] = [
                ft.Container(
                    content=ft.Text(str(day), color=TEXT, size=16, weight=ft.FontWeight.BOLD, no_wrap=True),
                    alignment=CENTER,
                    expand=True,
                )
            ]
            if has_docs:
                controls.append(
                    ft.Container(
                        width=8,
                        height=8,
                        bgcolor=GREEN,
                        border_radius=99,
                        right=8,
                        top=8,
                    )
                )
            async def open_day_click(_event, d=day):
                self.selected_day = d
                await self.with_loading("Abrindo dia...", self.show_day)

            return ft.Container(
                content=ft.Stack(controls=controls, expand=True),
                bgcolor="#10254a",
                border_radius=12,
                height=58,
                expand=1,
                on_click=open_day_click,
            )

        rows: list[ft.Control] = [
            ft.Row(
                [
                    ft.Container(
                        ft.Text(day, color=MUTED, size=11, weight=ft.FontWeight.BOLD, no_wrap=True),
                        alignment=CENTER,
                        expand=1,
                    )
                    for day in DIAS_SEMANA
                ],
                spacing=6,
            )
        ]
        for week in calendar.monthcalendar(year, month):
            week_controls: list[ft.Control] = []
            for day in week:
                if day == 0:
                    week_controls.append(ft.Container(height=58, expand=1))
                    continue
                week_controls.append(day_cell(day, day in days_with_docs))
            rows.append(ft.Row(week_controls, spacing=6))

        calendar_view = ft.Column(rows, spacing=10, horizontal_alignment=ft.CrossAxisAlignment.START)
        self.shell([header, self.card(calendar_view), self.button("Voltar aos meses", lambda _: self.show_dashboard())])

    def open_day(self, day: int) -> None:
        self.selected_day = day
        self.show_day()

    @property
    def data_str(self) -> str:
        return f"{date.today().year}-{self.selected_month:02d}-{self.selected_day:02d}"

    def show_day(self) -> None:
        if not self.selected_month or not self.selected_day:
            self.show_dashboard()
            return

        header = self.header(
            f"{self.selected_day:02d} de {MESES_PT[self.selected_month - 1]}",
            "Adicione, vincule e revise os documentos do dia.",
            False,
        )
        docs, links = self.load_day_docs()
        docs_by_id = {doc.id: doc for doc in docs}
        link_options = [ft.dropdown.Option(key="none", text="Nao vincular agora")]
        link_options.extend(ft.dropdown.Option(key=doc.id, text=nome_documento(doc)) for doc in docs)

        file_label = ft.Text(self.selected_file_name(), color=MUTED, size=12)

        def remember_type(event):
            self.selected_upload_type = event.control.value

        def remember_link_target(event):
            self.selected_link_target_id = event.control.value

        tipo = ft.Dropdown(
            label="Tipo do documento",
            value=self.selected_upload_type,
            options=[ft.dropdown.Option(item) for item in TIPOS_DOCUMENTO],
            bgcolor=PANEL_ALT,
            border_radius=12,
            on_select=remember_type,
        )
        link_target = ft.Dropdown(
            label="Vincular arquivos ao documento existente",
            value=self.selected_link_target_id if self.selected_link_target_id in docs_by_id else "none",
            options=link_options,
            bgcolor=PANEL_ALT,
            border_radius=12,
            on_select=remember_link_target,
        )
        link_selected_together = ft.Checkbox(
            label="Vincular arquivos selecionados entre si quando houver comprovante no lote",
            value=True,
            active_color=BLUE,
            check_color=TEXT,
        )

        upload_rows = self.upload_queue_controls()

        async def save(_):
            if not self.selected_upload_items:
                self.toast("Selecione um arquivo antes de salvar.", RED)
                return
            try:
                file_label.value = "Enviando..."
                self.page.update()
                def action():
                    uploaded_docs = [
                        self.documents.salvar_documento_do_arquivo(item["path"], self.data_str, item["type"])
                        for item in self.selected_upload_items
                    ]
                    target = docs_by_id.get(link_target.value)
                    if target:
                        for uploaded in uploaded_docs:
                            self.documents.salvar_vinculo(uploaded, target)
                    elif link_selected_together.value and len(uploaded_docs) > 1:
                        comprovantes = [doc for doc in uploaded_docs if doc.type == "comprovante"]
                        if comprovantes:
                            comprovante = comprovantes[0]
                            for uploaded in uploaded_docs:
                                if uploaded.id != comprovante.id:
                                    self.documents.salvar_vinculo(comprovante, uploaded)
                    return len(uploaded_docs)

                count = await self.with_loading("Salvando documentos...", action)
                self.selected_files = []
                self.selected_upload_items = []
                self.toast(f"{count} documento(s) salvo(s).", GREEN)
                self.show_day()
            except Exception as exc:
                file_label.value = self.selected_file_name()
                self.toast(str(exc), RED)
                self.page.update()

        upload = self.card(
            ft.Column(
                [
                    self.title("Adicionar documento", 16),
                    tipo,
                    file_label,
                    *upload_rows,
                    link_target,
                    link_selected_together,
                    ft.Row(
                        [
                            self.button("Arquivos", self.pick_file),
                            self.button("Salvar", save, primary=True),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ],
                spacing=10,
            )
        )

        doc_controls = self.document_sections(docs, links)
        self.shell([header, upload, *doc_controls, self.button("Voltar ao calendario", lambda _: self.show_calendar())])

    def selected_file_name(self) -> str:
        if not self.selected_files:
            return "Nenhum arquivo selecionado"
        if len(self.selected_files) == 1:
            return Path(self.selected_files[0]).name
        return f"{len(self.selected_files)} arquivos selecionados"

    def upload_queue_controls(self) -> list[ft.Control]:
        controls: list[ft.Control] = []
        for index, item in enumerate(self.selected_upload_items):
            type_dropdown = ft.Dropdown(
                label="Tipo",
                value=item["type"],
                options=[ft.dropdown.Option(option) for option in TIPOS_DOCUMENTO],
                bgcolor=PANEL_ALT,
                border_radius=12,
                expand=True,
                on_select=lambda event, idx=index: self.update_upload_item_type(idx, event.control.value),
            )
            controls.append(
                ft.Container(
                    bgcolor=PANEL_ALT,
                    border_radius=12,
                    padding=12,
                    content=ft.Column(
                        [
                            ft.Text(Path(item["path"]).name, color=TEXT, size=12, weight=ft.FontWeight.BOLD),
                            type_dropdown,
                        ],
                        spacing=8,
                    ),
                )
            )
        return controls

    def update_upload_item_type(self, index: int, doc_type: str) -> None:
        if 0 <= index < len(self.selected_upload_items):
            self.selected_upload_items[index]["type"] = doc_type
            self.selected_upload_type = doc_type

    async def pick_file(self, _event) -> None:
        files = await self.file_picker.pick_files(
            allow_multiple=True,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["pdf", "png", "jpg", "jpeg"],
        )
        if files:
            self.selected_files = [file.path for file in files if file.path]
            self.selected_upload_items = [
                {"path": file_path, "type": self.selected_upload_type}
                for file_path in self.selected_files
            ]
            self.show_day()

    def load_day_docs(self):
        try:
            docs = self.documents.listar_documentos_do_dia(self.data_str)
            links = self.documents.listar_links_documentos(docs)
            return docs, links
        except Exception as exc:
            self.toast(str(exc), RED)
            return [], []

    def document_sections(self, docs: list[Document], links) -> list[ft.Control]:
        if not docs:
            return [self.card(ft.Text("Nenhum documento adicionado ainda.", color=MUTED))]

        controls: list[ft.Control] = []
        docs_by_id = {doc.id: doc for doc in docs}
        used_ids: set[str] = set()
        grouped: dict[str, list[tuple]] = {}

        for link in links:
            primary = docs_by_id.get(link.comprovante_id)
            attached = docs_by_id.get(link.documento_id)
            if not primary or not attached:
                continue
            grouped.setdefault(primary.id, []).append((link, attached))
            used_ids.update({primary.id, attached.id})

        if grouped:
            controls.append(ft.Text("DOCUMENTOS VINCULADOS", color=MUTED, size=11, weight=ft.FontWeight.BOLD))
            for primary_id, attachments in grouped.items():
                controls.append(self.linked_group_card(docs_by_id[primary_id], attachments))

        loose_docs = [doc for doc in docs if doc.id not in used_ids]
        if loose_docs:
            controls.append(ft.Text("DOCUMENTOS AVULSOS", color=MUTED, size=11, weight=ft.FontWeight.BOLD))
            for doc in loose_docs:
                controls.append(self.document_card(doc, docs, links))
        return controls

    def linked_group_card(self, primary: Document, attachments: list[tuple]) -> ft.Control:
        rows: list[ft.Control] = [
            ft.Text(nome_documento(primary), color=TEXT, size=15, weight=ft.FontWeight.BOLD),
            ft.Text(f"{tipo_documento_label(primary.type)}  |  {primary.created_at[:10] or primary.date}", color=MUTED, size=11),
        ]
        for link, attached in attachments:
            rows.append(
                ft.Container(
                    bgcolor=PANEL_ALT,
                    border_radius=12,
                    padding=12,
                    content=ft.Column(
                        [
                            ft.Text(nome_documento(attached), color=TEXT, size=13, weight=ft.FontWeight.BOLD),
                            ft.Text(tipo_documento_label(attached.type), color=MUTED, size=11),
                            self.button("Desvincular", lambda _, item=link: self.unlink_document(item)),
                        ],
                        spacing=6,
                    ),
                )
            )
        return self.card(ft.Column(rows, spacing=10))

    def document_card(self, doc: Document, docs: list[Document], links) -> ft.Control:
        linked_ids = ids_vinculados(doc.id, links)
        linked_names = [nome_documento(item) for item in docs if item.id in linked_ids]
        link_text = f"Vinculado a: {', '.join(linked_names)}" if linked_names else "Sem vinculo"
        meta = f"{tipo_documento_label(doc.type)}  |  {doc.created_at[:10] or doc.date}  |  {link_text}"

        return self.card(
            ft.Column(
                [
                    ft.Text(nome_documento(doc), color=TEXT, size=15, weight=ft.FontWeight.BOLD),
                    ft.Text(meta, color=MUTED, size=11),
                    ft.Row(
                        [
                            self.button("Vincular", lambda _, item=doc: self.open_link_dialog(item, docs, links)),
                            self.button("Excluir", lambda _, item=doc: self.confirm_delete(item)),
                        ]
                    ),
                ],
                spacing=8,
            )
        )

    def open_link_dialog(self, source: Document, docs: list[Document], links) -> None:
        candidates = [item for item in docs if item.id != source.id and item.id not in ids_vinculados(source.id, links)]
        if not candidates:
            self.toast("Nao ha documentos disponiveis para vincular.", RED)
            return

        labels = {f"{tipo_documento_label(item.type)} | {nome_documento(item)}": item for item in candidates}
        selector = ft.Dropdown(value=list(labels.keys())[0], options=[ft.dropdown.Option(item) for item in labels])

        def confirm(_):
            target = labels[selector.value]
            self.close_dialog()
            try:
                ok = self.documents.salvar_vinculo(source, target)
                self.toast("Documento vinculado." if ok else "Esse vinculo ja existe.", GREEN if ok else YELLOW)
                self.show_day()
            except Exception as exc:
                self.toast(str(exc), RED)

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Vincular documento"),
            content=selector,
            actions=[self.button("Confirmar", confirm, primary=True), self.button("Cancelar", lambda _: self.close_dialog())],
        )
        self.show_dialog(dialog)

    def unlink_document(self, link) -> None:
        try:
            self.documents.desvincular_vinculo(link)
            self.toast("Documentos desvinculados.", GREEN)
            self.show_day()
        except Exception as exc:
            self.toast(str(exc), RED)

    def confirm_delete(self, doc: Document) -> None:
        def delete(_):
            self.close_dialog()
            try:
                self.documents.excluir_documento(doc)
                self.toast("Documento excluido.", GREEN)
                self.show_day()
            except Exception as exc:
                self.toast(str(exc), RED)

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirmar exclusao"),
            content=ft.Text(f"Excluir {nome_documento(doc)}?"),
            actions=[self.button("Excluir", delete, primary=True), self.button("Cancelar", lambda _: self.close_dialog())],
        )
        self.show_dialog(dialog)


def main(page: ft.Page) -> None:
    DocumentsOrgFletApp(page).run()


if __name__ == "__main__":
    ft.run(main)
