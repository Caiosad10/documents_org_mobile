from __future__ import annotations

import asyncio
import calendar
import html
import os
import shutil
import subprocess
import tempfile
import time
import webbrowser
from datetime import date
from pathlib import Path

import flet as ft

from documents_org.config.constants import DIAS_SEMANA, MESES_PT, TIPOS_DOCUMENTO
from documents_org.config.settings import load_settings
from documents_org.models import Document
from documents_org.services.document_service import DocumentService
from documents_org.services.rules import ids_vinculados, limpar_nome_arquivo, nome_documento, tipo_documento_label
from documents_org.services.supabase_client import SupabaseGateway


BG_TOP = "#0f1f3d"
BG = "#020617"
BG_BOTTOM = "#000000"
PANEL = "#0f1f3d"
PANEL_ALT = "#1e293b"
PANEL_HOVER = "#334155"
CARD_GRADIENT_END = "#060f1e"
LINE = "#1F3B82F6"
BORDER_SLATE = "#5994A3B8"
BORDER_BLUE_HOVER = "#CC60A5FA"
TEXT = "#f1f5f9"
TEXT_BODY = "#e5e7eb"
BUTTON_TEXT = "#e2e8f0"
BUTTON_TEXT_HOVER = "#f8fafc"
MUTED = "#cbd5e1"
FAINT = "#64748b"
BLUE = "#2563eb"
BLUE_HOVER = "#1d4ed8"
BLUE_SOFT = "#93c5fd"
BLUE_BORDER = "#4D3B82F6"
BLUE_SHADOW = "#663B82F6"
GREEN = "#86efac"
YELLOW = "#fde047"
RED = "#fca5a5"
SHADOW_CARD = "#66000000"
CENTER = ft.alignment.Alignment(0, 0)
MICRO_ANIMATION = ft.Animation(140, ft.AnimationCurve.EASE_OUT)
CARD_HOVER_SCALE = 1.012
DAY_HOVER_SCALE = 1.04


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


def background_gradient() -> ft.RadialGradient:
    return ft.RadialGradient(
        center=ft.alignment.Alignment(0, -1),
        radius=1.2,
        colors=[BG_TOP, BG, BG_BOTTOM],
        stops=[0, 0.5, 1],
    )


def card_gradient() -> ft.LinearGradient:
    return ft.LinearGradient(
        begin=ft.alignment.Alignment(-1, -1),
        end=ft.alignment.Alignment(1, 1),
        colors=[PANEL, CARD_GRADIENT_END],
    )


def hover_state(event) -> bool:
    return str(getattr(event, "data", "")).lower() == "true"


def apply_hover_scale(event, hovered_scale: float) -> None:
    event.control.scale = hovered_scale if hover_state(event) else 1
    event.control.update()


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
        self.selected_delete_ids: set[str] = set()
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
                bgcolor=BG_BOTTOM,
                gradient=background_gradient(),
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
                gradient=card_gradient(),
                border=border_all(1, BLUE_BORDER),
                border_radius=20,
                shadow=ft.BoxShadow(blur_radius=40, color=SHADOW_CARD, offset=ft.Offset(0, 18)),
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
            gradient=card_gradient(),
            border=border_all(1, LINE),
            border_radius=20,
            shadow=ft.BoxShadow(blur_radius=40, color=SHADOW_CARD, offset=ft.Offset(0, 18)),
            animate_scale=MICRO_ANIMATION,
        )

    def title(self, text: str, size=22) -> ft.Text:
        return ft.Text(text, size=size, weight=ft.FontWeight.BOLD, color=TEXT)

    def subtitle(self, text: str) -> ft.Text:
        return ft.Text(text, size=13, color=MUTED)

    def button(self, text: str, handler, primary=False) -> ft.Control:
        style = ft.ButtonStyle(
            bgcolor={
                ft.ControlState.DEFAULT: BLUE if primary else PANEL_ALT,
                ft.ControlState.HOVERED: BLUE_HOVER if primary else PANEL_HOVER,
            },
            color={
                ft.ControlState.DEFAULT: TEXT if primary else BUTTON_TEXT,
                ft.ControlState.HOVERED: BUTTON_TEXT_HOVER,
            },
            side={
                ft.ControlState.DEFAULT: ft.BorderSide(1, BLUE_BORDER if primary else BORDER_SLATE),
                ft.ControlState.HOVERED: ft.BorderSide(1, BORDER_BLUE_HOVER),
            },
            elevation={
                ft.ControlState.DEFAULT: 0,
                ft.ControlState.HOVERED: 6,
            },
            shadow_color={
                ft.ControlState.DEFAULT: "#00000000",
                ft.ControlState.HOVERED: BLUE_SHADOW,
            },
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=pad(horizontal=14, vertical=12),
            animation_duration=MICRO_ANIMATION.duration,
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

        card = self.card(
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
        card.on_hover = lambda event: apply_hover_scale(event, CARD_HOVER_SCALE)
        return card

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

            base_bg = PANEL if has_docs else PANEL_ALT
            base_border = BLUE_BORDER if has_docs else LINE

            def hover_day(event):
                hovered = hover_state(event)
                event.control.scale = DAY_HOVER_SCALE if hovered else 1
                event.control.bgcolor = PANEL_HOVER if hovered else base_bg
                event.control.border = border_all(1, BORDER_BLUE_HOVER if hovered else base_border)
                event.control.update()

            return ft.Container(
                content=ft.Stack(controls=controls, expand=True),
                bgcolor=base_bg,
                border=border_all(1, base_border),
                border_radius=12,
                height=58,
                expand=1,
                animate_scale=MICRO_ANIMATION,
                on_click=open_day_click,
                on_hover=hover_day,
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
        close_cash_card = self.card(
            ft.Column(
                [
                    self.title("Fechar caixa", 18),
                    self.subtitle("Veja todos os documentos do mes por ordem de dia, revise vinculos e pendencias."),
                    ft.Row(
                        [
                            self.button("Pre-fechamento", self.open_month_closing, primary=True),
                        ],
                        alignment=ft.MainAxisAlignment.END,
                    ),
                ],
                spacing=10,
            )
        )
        self.shell([
            header,
            close_cash_card,
            self.card(calendar_view),
            self.button("Voltar aos meses", lambda _: self.show_dashboard()),
        ])

    async def open_month_closing(self, _event) -> None:
        await self.with_loading("Montando pre-fechamento...", self.show_month_closing)

    def show_month_closing(self) -> None:
        if not self.selected_month:
            self.show_dashboard()
            return

        year = date.today().year
        month = self.selected_month
        docs = self.documents.listar_documentos_do_mes(year, month)
        links = self.documents.listar_links_documentos(docs)
        docs_by_id = {doc.id: doc for doc in docs}
        linked_by_comprovante: dict[str, list[Document]] = {}
        linked_doc_ids: set[str] = set()

        for link in links:
            comprovante = docs_by_id.get(link.comprovante_id)
            documento = docs_by_id.get(link.documento_id)
            if not comprovante or not documento:
                continue
            linked_by_comprovante.setdefault(comprovante.id, []).append(documento)
            linked_doc_ids.add(documento.id)

        comprovantes = [doc for doc in docs if doc.type == "comprovante"]
        pendentes = [doc for doc in comprovantes if doc.id not in linked_by_comprovante]
        days = sorted({doc.date for doc in docs})

        header = self.header(
            f"Pre-fechamento de {MESES_PT[month - 1]} {year}",
            "Revise os documentos do mes por ordem de dia antes de preparar a impressao.",
            False,
        )
        summary = self.closing_summary_card(len(days), len(docs), len(comprovantes), len(pendentes))
        controls: list[ft.Control] = [header, summary]

        if pendentes:
            controls.append(
                self.card(
                    ft.Column(
                        [
                            ft.Text("Pendencias", color=YELLOW, size=15, weight=ft.FontWeight.BOLD),
                            ft.Text(
                                f"{len(pendentes)} comprovante(s) sem vinculo. Corrija antes de imprimir.",
                                color=MUTED,
                                size=12,
                            ),
                        ],
                        spacing=6,
                    )
                )
            )

        if not docs:
            controls.append(self.card(ft.Text("Nenhum documento encontrado neste mes.", color=MUTED)))
        else:
            for day in days:
                day_docs = [doc for doc in docs if doc.date == day]
                controls.append(self.closing_day_card(day, day_docs, linked_by_comprovante, linked_doc_ids))

        async def export_print(_event):
            try:
                path = await self.with_loading(
                    "Gerando HTML de impressao...",
                    lambda: self.export_month_closing_html(year, month, docs, links),
                )
                try:
                    webbrowser.open(path.resolve().as_uri())
                    self.toast("HTML de impressao gerado e aberto no navegador.", GREEN)
                except Exception:
                    self.toast(f"HTML gerado em: {path}", GREEN)
            except Exception as exc:
                self.toast(str(exc), RED)

        async def print_queue(_event):
            try:
                total = await self.with_loading(
                    "Enviando documentos para impressao...",
                    lambda: self.print_month_closing_documents(year, month, docs, links),
                )
                self.toast(f"{total} documento(s) enviados para impressao.", GREEN)
            except Exception as exc:
                self.toast(str(exc), RED)

        controls.append(
            self.card(
                ft.Column(
                    [
                        self.title("Impressao", 16),
                        self.subtitle("Imprima a fila do mes em ordem de dia ou gere um HTML apenas para conferencia visual."),
                        ft.Row(
                            [
                                self.button("Imprimir fila automaticamente", print_queue, primary=True),
                                self.button("Gerar HTML de conferencia", export_print),
                            ],
                            spacing=8,
                            wrap=True,
                        ),
                    ],
                    spacing=10,
                )
            )
        )
        controls.append(self.button("Voltar ao calendario", lambda _: self.show_calendar()))
        self.shell(controls)

    def closing_summary_card(self, total_days: int, total_docs: int, total_comprovantes: int, total_pendentes: int) -> ft.Control:
        status_color = GREEN if total_pendentes == 0 else YELLOW
        status_text = "Pronto para conferencia" if total_pendentes == 0 else "Pendencias para revisar"
        return self.card(
            ft.Column(
                [
                    ft.Text(status_text, color=status_color, size=15, weight=ft.FontWeight.BOLD),
                    ft.Row(
                        [
                            self.metric_box("Dias", total_days),
                            self.metric_box("Docs", total_docs),
                            self.metric_box("Comprovantes", total_comprovantes),
                            self.metric_box("Pendentes", total_pendentes, color=status_color),
                        ],
                        spacing=8,
                        wrap=True,
                    ),
                ],
                spacing=12,
            )
        )

    def metric_box(self, label: str, value: int, color: str = TEXT) -> ft.Control:
        return ft.Container(
            bgcolor=PANEL_ALT,
            border=border_all(1, LINE),
            border_radius=12,
            padding=12,
            content=ft.Column(
                [
                    ft.Text(str(value), color=color, size=20, weight=ft.FontWeight.BOLD),
                    ft.Text(label, color=MUTED, size=11),
                ],
                spacing=2,
                tight=True,
            ),
        )

    def closing_day_card(
        self,
        day: str,
        docs: list[Document],
        linked_by_comprovante: dict[str, list[Document]],
        linked_doc_ids: set[str],
    ) -> ft.Control:
        day_number = int(day.split("-")[2])

        async def open_day(_event, selected=day_number):
            self.selected_day = selected
            await self.with_loading("Abrindo dia...", self.show_day)

        rows: list[ft.Control] = [
            ft.Row(
                [
                    ft.Text(f"{day_number:02d} de {MESES_PT[self.selected_month - 1]}", color=TEXT, size=16, weight=ft.FontWeight.BOLD, expand=True),
                    self.button("Abrir dia", open_day),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
        ]

        for doc in docs:
            if doc.id in linked_doc_ids:
                continue
            if doc.type == "comprovante":
                linked_docs = linked_by_comprovante.get(doc.id, [])
                rows.append(self.closing_document_line(doc, linked_docs, pending=not linked_docs))
            else:
                rows.append(self.closing_document_line(doc, [], pending=False))

        return self.card(ft.Column(rows, spacing=10))

    def closing_document_line(self, doc: Document, linked_docs: list[Document], pending: bool) -> ft.Control:
        if linked_docs:
            detail = "Vinculado a: " + ", ".join(nome_documento(item) for item in linked_docs)
            status_color = GREEN
        elif pending:
            detail = "Sem vinculo"
            status_color = YELLOW
        else:
            detail = "Documento avulso"
            status_color = MUTED

        return ft.Container(
            bgcolor=PANEL_ALT,
            border=border_all(1, LINE),
            border_radius=12,
            padding=12,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(nome_documento(doc), color=TEXT, size=13, weight=ft.FontWeight.BOLD, expand=True),
                            ft.Text(tipo_documento_label(doc.type), color=status_color, size=11, weight=ft.FontWeight.BOLD),
                        ],
                        spacing=8,
                    ),
                    ft.Text(detail, color=MUTED, size=11),
                ],
                spacing=5,
            ),
        )

    def export_month_closing_html(
        self,
        year: int,
        month: int,
        docs: list[Document],
        links,
        output_dir: Path | None = None,
    ) -> Path:
        output_dir = output_dir or Path(tempfile.gettempdir()) / "documents_org_mobile_print"
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"fechamento_{year}_{month:02d}.html"
        assets_dir = output_dir / f"fechamento_{year}_{month:02d}_arquivos"

        try:
            ordered_docs, document_paths, assets_dir = self.prepare_month_print_files(year, month, docs, links, output_dir)
            document_sources = {
                doc.id: f"{assets_dir.name}/{document_paths[doc.id].name}"
                for doc in ordered_docs
                if doc.id in document_paths
            }

            path.write_text(
                self.build_month_closing_html(year, month, docs, links, document_sources),
                encoding="utf-8",
            )
        except Exception:
            self.clean_print_assets_dir(assets_dir)
            try:
                if path.exists():
                    path.unlink()
            except PermissionError:
                pass
            raise
        return path

    def prepare_month_print_files(
        self,
        year: int,
        month: int,
        docs: list[Document],
        links,
        output_dir: Path | None = None,
    ) -> tuple[list[Document], dict[str, Path], Path]:
        output_dir = output_dir or Path(tempfile.gettempdir()) / "documents_org_mobile_print"
        output_dir.mkdir(parents=True, exist_ok=True)
        assets_dir = output_dir / f"fechamento_{year}_{month:02d}_arquivos"
        if assets_dir.exists():
            self.clean_print_assets_dir(assets_dir)
        assets_dir.mkdir(parents=True, exist_ok=True)

        ordered_docs = self.ordered_closing_documents(docs, links)
        document_paths: dict[str, Path] = {}
        for index, doc in enumerate(ordered_docs, start=1):
            doc_name = nome_documento(doc)
            file_name = f"{index:03d}_{doc.date}_{limpar_nome_arquivo(doc_name)}"
            target = assets_dir / file_name
            try:
                target.write_bytes(self.documents.baixar_documento(doc))
            except Exception as exc:
                self.clean_print_assets_dir(assets_dir)
                raise RuntimeError(f"Falha ao baixar {doc_name}: {exc}") from exc
            document_paths[doc.id] = target

        return ordered_docs, document_paths, assets_dir

    def clean_print_assets_dir(self, assets_dir: Path) -> None:
        if not assets_dir.exists():
            return
        for child in assets_dir.iterdir():
            try:
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    child.unlink()
            except PermissionError:
                pass
        try:
            assets_dir.rmdir()
        except OSError:
            pass

    def print_month_closing_documents(
        self,
        year: int,
        month: int,
        docs: list[Document],
        links,
        output_dir: Path | None = None,
    ) -> int:
        ordered_docs, document_paths, assets_dir = self.prepare_month_print_files(year, month, docs, links, output_dir)
        printed = 0
        try:
            for doc in ordered_docs:
                path = document_paths.get(doc.id)
                if not path:
                    continue
                self.print_local_file(path)
                printed += 1
                size_mb = max(path.stat().st_size / (1024 * 1024), 0.1)
                time.sleep(max(4, min(30, size_mb * 3)))
        finally:
            self.clean_print_assets_dir(assets_dir)
        return printed

    def print_local_file(self, path: Path) -> None:
        path = path.resolve()
        if not path.exists():
            raise RuntimeError(f"Arquivo nao encontrado para impressao: {path.name}")

        command = self.print_command_for_file(path)
        if command:
            subprocess.Popen(command)
            return

        if os.name == "nt":
            os.startfile(str(path), "print")  # type: ignore[attr-defined]
            return

        raise RuntimeError("Impressao automatica disponivel apenas no Windows nesta versao.")

    def print_command_for_file(self, path: Path) -> list[str] | None:
        if path.suffix.lower() != ".pdf":
            return None

        local_appdata = Path(os.getenv("LOCALAPPDATA", ""))
        sumatra_candidates = [
            local_appdata / "SumatraPDF" / "SumatraPDF.exe",
            Path("C:/Program Files/SumatraPDF/SumatraPDF.exe"),
            Path("C:/Program Files (x86)/SumatraPDF/SumatraPDF.exe"),
        ]
        for exe in sumatra_candidates:
            if exe.exists():
                return [str(exe), "-print-to-default", "-silent", str(path)]

        adobe_candidates = [
            Path("C:/Program Files/Adobe/Acrobat DC/Acrobat/Acrobat.exe"),
            Path("C:/Program Files/Adobe/Acrobat/Acrobat.exe"),
            Path("C:/Program Files/Adobe/Acrobat Reader DC/Reader/AcroRd32.exe"),
            Path("C:/Program Files (x86)/Adobe/Acrobat Reader DC/Reader/AcroRd32.exe"),
        ]
        for exe in adobe_candidates:
            if exe.exists():
                return [str(exe), "/N", "/T", str(path)]

        return None

    def ordered_closing_documents(self, docs: list[Document], links) -> list[Document]:
        docs_by_id = {doc.id: doc for doc in docs}
        linked_by_comprovante: dict[str, list[Document]] = {}
        linked_doc_ids: set[str] = set()

        for link in links:
            comprovante = docs_by_id.get(link.comprovante_id)
            documento = docs_by_id.get(link.documento_id)
            if not comprovante or not documento:
                continue
            linked_by_comprovante.setdefault(comprovante.id, []).append(documento)
            linked_doc_ids.add(documento.id)

        ordered: list[Document] = []
        for day in sorted({doc.date for doc in docs}):
            for doc in [item for item in docs if item.date == day]:
                if doc.id in linked_doc_ids:
                    continue
                ordered.append(doc)
                for linked in linked_by_comprovante.get(doc.id, []):
                    ordered.append(linked)
        return ordered

    def build_month_closing_html(
        self,
        year: int,
        month: int,
        docs: list[Document],
        links,
        document_sources: dict[str, str] | None = None,
    ) -> str:
        document_sources = document_sources or {}
        ordered_docs = self.ordered_closing_documents(docs, links)

        def esc(value: str) -> str:
            return html.escape(value or "")

        def document_viewer(doc: Document) -> str:
            source = document_sources.get(doc.id, "")
            ext = Path(source or nome_documento(doc)).suffix.lower()
            if not source:
                body = f'<div class="missing">Arquivo nao exportado: {esc(doc.file_path)}</div>'
            elif ext in {".png", ".jpg", ".jpeg"}:
                body = f'<img class="document-image" src="{esc(source)}" alt="{esc(nome_documento(doc))}" />'
            elif ext == ".pdf":
                body = f"""
                    <object class="document-frame" data="{esc(source)}" type="application/pdf">
                        <p>PDF nao exibido pelo navegador. Abra o arquivo: <a href="{esc(source)}">{esc(nome_documento(doc))}</a></p>
                    </object>
                """
            else:
                body = f'<p>Formato nao incorporado. Abra o arquivo: <a href="{esc(source)}">{esc(nome_documento(doc))}</a></p>'

            return f"""
                <section class="sheet">
                    <div class="sheet-header">
                        <div>
                            <strong>{esc(doc.date)}</strong>
                            <span>{esc(tipo_documento_label(doc.type))}</span>
                        </div>
                        <div class="file-name">{esc(nome_documento(doc))}</div>
                    </div>
                    {body}
                </section>
            """

        document_sections = "".join(document_viewer(doc) for doc in ordered_docs)
        total_days = len({doc.date for doc in docs})

        return f"""<!doctype html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8" />
    <title>Documentos para impressao - {esc(MESES_PT[month - 1])} {year}</title>
    <style>
        :root {{
            color-scheme: light;
            --text: #111827;
            --muted: #64748b;
            --line: #cbd5e1;
            --soft: #f8fafc;
            --ok: #166534;
            --warn: #b45309;
            --danger: #b91c1c;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            padding: 24px;
            color: var(--text);
            font-family: Arial, Helvetica, sans-serif;
            background: white;
        }}
        .actions {{
            position: sticky;
            top: 0;
            padding-bottom: 16px;
            background: white;
            text-align: right;
            z-index: 2;
        }}
        button {{
            border: 0;
            border-radius: 8px;
            padding: 10px 16px;
            color: white;
            background: #2563eb;
            font-weight: 700;
            cursor: pointer;
        }}
        header {{
            border-bottom: 2px solid var(--text);
            margin-bottom: 20px;
            padding-bottom: 16px;
        }}
        h1 {{ margin: 0 0 6px 0; font-size: 28px; }}
        .subtitle {{ color: var(--muted); }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(3, minmax(120px, 1fr));
            gap: 10px;
            margin: 20px 0;
        }}
        .metric {{
            border: 1px solid var(--line);
            border-radius: 10px;
            padding: 12px;
            background: var(--soft);
        }}
        .metric strong {{ display: block; font-size: 24px; }}
        .metric span {{ color: var(--muted); font-size: 12px; }}
        .sheet {{
            break-after: page;
            page-break-after: always;
            border: 1px solid var(--line);
            border-radius: 10px;
            min-height: calc(100vh - 72px);
            margin-bottom: 24px;
            overflow: hidden;
        }}
        .sheet-header {{
            display: flex;
            justify-content: space-between;
            gap: 12px;
            align-items: center;
            padding: 10px 12px;
            border-bottom: 1px solid var(--line);
            background: var(--soft);
        }}
        .sheet-header span {{
            display: block;
            color: var(--muted);
            font-size: 12px;
            font-weight: 700;
        }}
        .file-name {{
            color: var(--muted);
            font-size: 12px;
            text-align: right;
            max-width: 52%;
        }}
        .document-frame {{
            display: block;
            width: 100%;
            height: calc(100vh - 130px);
            border: 0;
        }}
        .document-image {{
            display: block;
            max-width: 100%;
            max-height: calc(100vh - 130px);
            margin: 0 auto;
            object-fit: contain;
        }}
        .missing {{
            padding: 24px;
            color: var(--danger);
            font-weight: 700;
        }}
        @media print {{
            body {{ padding: 0; }}
            .actions, header, .summary {{ display: none; }}
            .sheet {{
                border: 0;
                border-radius: 0;
                min-height: 100vh;
                margin: 0;
            }}
            .sheet-header {{
                padding: 5mm 8mm;
            }}
            .document-frame, .document-image {{
                height: calc(100vh - 24mm);
            }}
        }}
    </style>
</head>
<body>
    <div class="actions"><button onclick="window.print()">Imprimir</button></div>
    <header>
        <h1>Documentos para impressao - {esc(MESES_PT[month - 1])} {year}</h1>
        <div class="subtitle">Arquivos reais ordenados por dia. Documentos vinculados aparecem em sequencia para facilitar o grampeamento.</div>
    </header>
    <div class="summary">
        <div class="metric"><strong>{total_days}</strong><span>Dias com documentos</span></div>
        <div class="metric"><strong>{len(docs)}</strong><span>Documentos</span></div>
        <div class="metric"><strong>{len(ordered_docs)}</strong><span>Paginas/arquivos</span></div>
    </div>
    {document_sections if document_sections else '<p>Nenhum documento encontrado neste mes.</p>'}
</body>
</html>
"""

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
        self.prune_delete_selection(docs)
        docs_by_id = {doc.id: doc for doc in docs}
        link_options = [ft.dropdown.Option(key="none", text="Nao vincular agora")]
        link_options.extend(ft.dropdown.Option(key=doc.id, text=nome_documento(doc)) for doc in docs)

        file_label = ft.Text(self.selected_file_name(), color=MUTED, size=12)

        def remember_type(event):
            self.selected_upload_type = event.control.value

        tipo = ft.Dropdown(
            label="Tipo do documento",
            value=self.selected_upload_type,
            options=[ft.dropdown.Option(item) for item in TIPOS_DOCUMENTO],
            bgcolor=PANEL_ALT,
            border_radius=12,
            on_select=remember_type,
        )

        upload_rows = self.upload_queue_controls(docs)

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
                    uploaded_by_key = {
                        item["key"]: uploaded
                        for item, uploaded in zip(self.selected_upload_items, uploaded_docs)
                    }
                    for item, uploaded in zip(self.selected_upload_items, uploaded_docs):
                        target_id = item.get("link_target", "none")
                        target = docs_by_id.get(target_id) or uploaded_by_key.get(target_id)
                        if target and target.id != uploaded.id:
                            self.documents.salvar_vinculo(uploaded, target)
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

    def upload_queue_controls(self, existing_docs: list[Document] | None = None) -> list[ft.Control]:
        controls: list[ft.Control] = []
        existing_docs = existing_docs or []
        for index, item in enumerate(self.selected_upload_items):
            link_options = [ft.dropdown.Option(key="none", text="Nao vincular agora")]
            for doc in existing_docs:
                link_options.append(ft.dropdown.Option(key=doc.id, text=f"Ja salvo | {nome_documento(doc)}"))
            for other_index, other in enumerate(self.selected_upload_items):
                if other_index == index:
                    continue
                link_options.append(ft.dropdown.Option(key=other["key"], text=f"Selecionado | {Path(other['path']).name}"))

            type_dropdown = ft.Dropdown(
                label="Tipo",
                value=item["type"],
                options=[ft.dropdown.Option(option) for option in TIPOS_DOCUMENTO],
                bgcolor=PANEL_ALT,
                border_radius=12,
                expand=True,
                on_select=lambda event, idx=index: self.update_upload_item_type(idx, event.control.value),
            )
            link_dropdown = ft.Dropdown(
                label="Vincular este arquivo a",
                value=item.get("link_target", "none"),
                options=link_options,
                bgcolor=PANEL_ALT,
                border_radius=12,
                expand=True,
                on_select=lambda event, idx=index: self.update_upload_item_link_target(idx, event.control.value),
            )
            controls.append(
                ft.Container(
                    bgcolor=PANEL_ALT,
                    border=border_all(1, LINE),
                    border_radius=12,
                    padding=12,
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(
                                        Path(item["path"]).name,
                                        color=TEXT,
                                        size=12,
                                        weight=ft.FontWeight.BOLD,
                                        expand=True,
                                        max_lines=2,
                                    ),
                                    ft.Button(
                                        "X",
                                        on_click=lambda _event, idx=index: self.remove_upload_item(idx),
                                        width=42,
                                        height=36,
                                        style=ft.ButtonStyle(
                                            bgcolor=PANEL_HOVER,
                                            color=RED,
                                            shape=ft.RoundedRectangleBorder(radius=10),
                                            padding=pad(horizontal=8, vertical=8),
                                        ),
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                spacing=8,
                            ),
                            type_dropdown,
                            link_dropdown,
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

    def update_upload_item_link_target(self, index: int, target: str) -> None:
        if 0 <= index < len(self.selected_upload_items):
            self.selected_upload_items[index]["link_target"] = target

    def remove_upload_item(self, index: int) -> None:
        if 0 <= index < len(self.selected_upload_items):
            removed_key = self.selected_upload_items[index]["key"]
            self.selected_upload_items.pop(index)
            for item in self.selected_upload_items:
                if item.get("link_target") == removed_key:
                    item["link_target"] = "none"
            self.selected_files = [item["path"] for item in self.selected_upload_items]
            self.show_day()

    async def pick_file(self, _event) -> None:
        files = await self.file_picker.pick_files(
            allow_multiple=True,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["pdf", "png", "jpg", "jpeg"],
        )
        if files:
            self.selected_files = [file.path for file in files if file.path]
            self.selected_upload_items = [
                {"key": f"selected-{index}", "path": file_path, "type": self.selected_upload_type, "link_target": "none"}
                for index, file_path in enumerate(self.selected_files)
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

        controls: list[ft.Control] = [self.bulk_delete_card(docs)]
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

    def bulk_delete_card(self, docs: list[Document]) -> ft.Control:
        selected_count = len(self.selected_delete_ids)
        total = len(docs)
        status = f"{selected_count} de {total} selecionado(s)"
        return self.card(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    self.title("Selecao para exclusao", 15),
                                    self.subtitle(status),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.Row(
                                [
                                    self.button("Selecionar todos", lambda _: self.select_all_documents(docs)),
                                    self.button("Limpar", lambda _: self.clear_delete_selection()),
                                    self.button("Excluir selecionados", lambda _: self.confirm_delete_selected(docs), primary=True),
                                ],
                                spacing=8,
                                wrap=True,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                ],
                spacing=8,
            )
        )

    def prune_delete_selection(self, docs: list[Document]) -> None:
        valid_ids = {doc.id for doc in docs}
        self.selected_delete_ids.intersection_update(valid_ids)

    def toggle_delete_selection(self, doc_id: str, selected: bool) -> None:
        if selected:
            self.selected_delete_ids.add(doc_id)
        else:
            self.selected_delete_ids.discard(doc_id)

    def select_all_documents(self, docs: list[Document]) -> None:
        self.selected_delete_ids = {doc.id for doc in docs}
        self.show_day()

    def clear_delete_selection(self) -> None:
        self.selected_delete_ids.clear()
        self.show_day()

    def selection_checkbox(self, doc: Document) -> ft.Control:
        return ft.Checkbox(
            value=doc.id in self.selected_delete_ids,
            active_color=BLUE,
            check_color=TEXT,
            on_change=lambda event, item=doc: self.toggle_delete_selection(item.id, bool(event.control.value)),
        )

    def linked_group_card(self, primary: Document, attachments: list[tuple]) -> ft.Control:
        rows: list[ft.Control] = [
            ft.Row(
                [
                    self.selection_checkbox(primary),
                    ft.Column(
                        [
                            ft.Text(nome_documento(primary), color=TEXT, size=15, weight=ft.FontWeight.BOLD),
                            ft.Text(f"{tipo_documento_label(primary.type)}  |  {primary.created_at[:10] or primary.date}", color=MUTED, size=11),
                        ],
                        spacing=4,
                        expand=True,
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
        ]
        for link, attached in attachments:
            rows.append(
                ft.Container(
                    bgcolor=PANEL_ALT,
                    border=border_all(1, LINE),
                    border_radius=12,
                    padding=12,
                    content=ft.Row(
                        [
                            self.selection_checkbox(attached),
                            ft.Column(
                                [
                                    ft.Text(nome_documento(attached), color=TEXT, size=13, weight=ft.FontWeight.BOLD),
                                    ft.Text(tipo_documento_label(attached.type), color=MUTED, size=11),
                                    self.button("Desvincular", lambda _, item=link: self.unlink_document(item)),
                                ],
                                spacing=6,
                                expand=True,
                            ),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.START,
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
                    ft.Row(
                        [
                            self.selection_checkbox(doc),
                            ft.Column(
                                [
                                    ft.Text(nome_documento(doc), color=TEXT, size=15, weight=ft.FontWeight.BOLD),
                                    ft.Text(meta, color=MUTED, size=11),
                                ],
                                spacing=5,
                                expand=True,
                            ),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
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
        linked_ids = ids_vinculados(source.id, links)
        if source.type == "comprovante":
            candidates = [
                item for item in docs
                if item.id != source.id and item.id not in linked_ids and item.type != "comprovante"
            ]
        else:
            candidates = [
                item for item in docs
                if item.id != source.id and item.id not in linked_ids and item.type == "comprovante"
            ]
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
                self.selected_delete_ids.discard(doc.id)
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

    def confirm_delete_selected(self, docs: list[Document]) -> None:
        selected_docs = [doc for doc in docs if doc.id in self.selected_delete_ids]
        if not selected_docs:
            self.toast("Selecione ao menos um documento para excluir.", RED)
            return

        preview_names = [nome_documento(doc) for doc in selected_docs[:5]]
        preview = "\n".join(f"- {name}" for name in preview_names)
        if len(selected_docs) > 5:
            preview += f"\n... e mais {len(selected_docs) - 5} documento(s)."

        async def delete(_):
            self.close_dialog()

            def action():
                for doc in selected_docs:
                    self.documents.excluir_documento(doc)
                return len(selected_docs)

            try:
                count = await self.with_loading("Excluindo documentos...", action)
                for doc in selected_docs:
                    self.selected_delete_ids.discard(doc.id)
                self.toast(f"{count} documento(s) excluido(s).", GREEN)
                self.show_day()
            except Exception as exc:
                self.toast(str(exc), RED)

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirmar exclusao em lote"),
            content=ft.Text(
                f"Excluir {len(selected_docs)} documento(s)?\n\n"
                "Esta acao remove os vinculos, o registro no banco e tenta remover o arquivo do Storage.\n\n"
                f"{preview}"
            ),
            actions=[
                self.button("Excluir documentos", delete, primary=True),
                self.button("Cancelar", lambda _: self.close_dialog()),
            ],
        )
        self.show_dialog(dialog)


def main(page: ft.Page) -> None:
    DocumentsOrgFletApp(page).run()


if __name__ == "__main__":
    ft.run(main)
