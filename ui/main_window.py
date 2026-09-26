"""
===========================================================
PRT Nexus - Main Window & Sidebar
Description: Janela principal com integração total da PRTSidebar e QStackedWidget.
===========================================================
"""
from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from database.manager import db_manager, plataforma_da_url
from theme.colors import ThemeColors
from ui.views.browser_view import BrowserView
from ui.views.chip7_view import Chip7View
from ui.views.downloads_view import DownloadsView
from ui.views.drive_view import DriveView
from ui.views.favorites_view import FavoritesView
from ui.views.greenn_view import GreennView
from ui.views.history_view import HistoryView
from ui.views.hotmart_view import HotmartView
from ui.views.home_view import HomeView
from ui.views.kiwify_view import KiwifyView
from ui.views.library_view import LibraryView
from ui.views.license_view import LicenseView
from ui.views.mega_view import MegaView
from ui.views.settings_view import SettingsView
from ui.views.tiktok_view import TikTokView
from ui.views.youtube_view import YouTubeView
from ui.views.universo_view import UniversoView
from ui.views.vimeo_view import VimeoView


def svg_to_icon(svg_code: str, size: int = 64) -> QIcon:
    """Converte strings SVG diretamente em QIcon vetorial HD."""
    renderer = QSvgRenderer(bytes(svg_code, "utf-8"))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


SVG_ICONS = {
    "bolt": '<svg viewBox="0 0 24 24" fill="#F59E0B"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>',
    "home": '<svg viewBox="0 0 24 24" fill="none" stroke="#A1A1AA" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>',
    "globe": '<svg viewBox="0 0 24 24" fill="none" stroke="#A1A1AA" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10z"/></svg>',
    "download": '<svg viewBox="0 0 24 24" fill="none" stroke="#A1A1AA" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>',
    "folder": '<svg viewBox="0 0 24 24" fill="none" stroke="#A1A1AA" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>',
    "star": '<svg viewBox="0 0 24 24" fill="none" stroke="#A1A1AA" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
    "clock": '<svg viewBox="0 0 24 24" fill="none" stroke="#A1A1AA" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
    "youtube": '<svg viewBox="0 0 24 24" fill="#FF0000"><path d="M23.5 6.2a3 3 0 0 0-2.1-2.1C19.5 3.5 12 3.5 12 3.5s-7.5 0-9.4.5A3 3 0 0 0 .5 6.2C0 8.1 0 12 0 12s0 3.9.5 5.8a3 3 0 0 0 2.1 2.1c1.9.5 9.4.5 9.4.5s7.5 0 9.4-.5a3 3 0 0 0 2.1-2.1c.5-1.9.5-5.8.5-5.8s0-3.9-.5-5.8zM9.5 15.5V8.5l6.3 3.5-6.3 3.5z"/></svg>',
    "tiktok": '<svg viewBox="0 0 24 24" fill="#25F4EE"><path d="M12.5 2h3a5.5 5.5 0 0 0 5.5 5.5v3a8.5 8.5 0 0 1-5.5-2V15a6.5 6.5 0 1 1-6.5-6.5c.3 0 .7 0 1 .1V12a3.5 3.5 0 1 0 2.5 3.4V2z"/></svg>',
    "kiwify": '<svg viewBox="0 0 24 24" fill="none"><path d="M 18.5 16 A 8.5 8.5 0 1 1 8.5 3.5" stroke="#00A859" stroke-width="3.2" stroke-linecap="round"/><ellipse cx="8.5" cy="8.5" rx="1" ry="1.8" transform="rotate(-40 8.5 8.5)" fill="#00A859"/><ellipse cx="7.2" cy="12" rx="1" ry="1.8" transform="rotate(-10 7.2 12)" fill="#00A859"/><ellipse cx="8.5" cy="15.5" rx="1" ry="1.8" transform="rotate(25 8.5 15.5)" fill="#00A859"/><ellipse cx="12" cy="17.2" rx="1" ry="1.8" transform="rotate(60 12 17.2)" fill="#00A859"/></svg>',
    "hotmart": '<svg viewBox="0 0 24 24" fill="#FF3E00"><path fill-rule="evenodd" clip-rule="evenodd" d="M12 0.5C10.2 3.2 8.8 5 6.5 6.2C7.2 4.4 7 3 6.8 1.8C3.8 4.2 2 7.8 2 12C2 17.5 6.5 22 12 22C17.5 22 22 17.5 22 12C22 7.8 20.2 4.2 17.2 1.8C17 3 16.8 4.4 17.5 6.2C15.2 5 13.8 3.2 12 0.5ZM12 17.2A4.2 4.2 0 1 0 12 8.8A4.2 4.2 0 1 0 12 17.2Z"/></svg>',
    "vimeo": '<svg viewBox="0 0 24 24" fill="#1AB7EA"><path d="M22.396 7.164c-.093 2.026-1.507 4.8-4.239 8.321-2.822 3.682-5.202 5.523-7.143 5.523-1.203 0-2.217-1.112-3.042-3.336L5.334 10.97C4.69 8.71 4.025 7.58 3.338 7.58c-.14 0-.635.298-1.487.895L0 7.218c1.314-1.155 2.607-2.308 3.882-3.46 1.742-.152 2.996.993 3.764 3.435.82 2.604 1.393 4.223 1.718 4.855.727 1.115 1.39 1.672 1.99 1.672.6 0 1.29-.418 2.072-1.254.782-.836 1.233-1.82 1.353-2.952.23-1.98-.992-2.935-3.666-2.865 1.11-3.63 3.238-5.367 6.386-5.212 2.33.115 3.754 1.38 3.947 3.737z"/></svg>',
    "greenn": '<svg viewBox="0 0 64 76" fill="none"><defs><linearGradient id="greennMenu" x1="8" y1="4" x2="56" y2="70" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#D4F562"/><stop offset="0.5" stop-color="#2FDB8A"/><stop offset="1" stop-color="#14C6DE"/></linearGradient></defs><circle cx="32" cy="30" r="19" stroke="url(#greennMenu)" stroke-width="9"/><path fill="url(#greennMenu)" d="M25 47h14l-7 16z"/><path d="M21 31l8 8 15-16" stroke="url(#greennMenu)" stroke-width="5.4" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "drive": '<svg viewBox="0 0 24 24"><path fill="#1A73E8" d="M8.7 3.5L2.1 15h6.6l6.6-11.5H8.7z"/><path fill="#FFC107" d="M15.3 3.5H8.7l6.6 11.5h6.6L15.3 3.5z"/><path fill="#0F9D58" d="M2.1 15l3.3 5.7h13.2l-3.3-5.7H2.1z"/></svg>',
    "mega": '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="#D9272E"/><path d="M7 15V9l5 4 5-4v6" stroke="#FFF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>',
    "universo": '<svg viewBox="0 0 24 24" fill="none" stroke="#00D2FF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10z"/></svg>',
    "chip7": '<svg viewBox="0 0 24 24" fill="#A1A1A6"><path d="M18.7 19.5c-.8 1.2-1.7 2.5-3.1 2.5-1.3 0-1.8-.8-3.3-.8-1.5 0-2 .8-3.3.8-1.3 0-2.3-1.3-3.1-2.5C4.2 17 2.9 12.5 4.7 9.4c.9-1.5 2.4-2.5 4.1-2.5 1.3 0 2.5.9 3.3.9.8 0 2.3-1.1 3.8-.9.6 0 2.5.3 3.6 2-.1.1-2.2 1.3-2.1 3.8.1 3 2.6 4 2.7 4-.1.1-.4 1.4-1.4 2.8M13 3.5c.7-.8 1.2-2 1.1-3.1-1 .1-2.2.7-2.9 1.5-.6.7-1.2 1.9-1 3 .1 0 .2 0 .3 0 1 0 2.2-.6 2.5-1.4z"/></svg>',
    "settings": '<svg viewBox="0 0 24 24" fill="none" stroke="#A1A1AA" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
    "lock": '<svg viewBox="0 0 24 24" fill="none" stroke="#A1A1AA" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>',
    "refresh": '<svg viewBox="0 0 24 24" fill="none" stroke="#A1A1AA" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>',
    "plugin": '<svg viewBox="0 0 24 24" fill="none" stroke="#A1A1AA" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>',
}


class PRTSidebar(QWidget):
    """Sidebar moderna estilo Linear/Vercel Dark Theme."""

    navigate_requested = Signal(str)
    navigation_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(228)
        self.buttons: list[QPushButton] = []
        self._secoes: list[QLabel] = []
        self._ativo: QPushButton | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 16, 10, 16)
        main_layout.setSpacing(6)

        # Cabeçalho
        header_container = QWidget()
        header_container.setStyleSheet("background: transparent; border: none;")
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(2, 0, 2, 10)
        header_layout.setSpacing(8)

        self.logo_box = QLabel()
        self.logo_box.setFixedSize(40, 40)
        self.logo_box.setPixmap(svg_to_icon(SVG_ICONS["bolt"], 24).pixmap(24, 24))
        self.logo_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.logo_box)

        titles_layout = QVBoxLayout()
        titles_layout.setContentsMargins(0, 0, 0, 0)
        titles_layout.setSpacing(2)

        self.lbl_title = QLabel("PRT Nexus")
        self.lbl_subtitle = QLabel("ULTRA DOWNLOADER")

        titles_layout.addWidget(self.lbl_title)
        titles_layout.addWidget(self.lbl_subtitle)
        header_layout.addLayout(titles_layout)
        header_layout.addStretch()

        main_layout.addWidget(header_container)

        # Divisor
        self.divisor = QFrame()
        self.divisor.setFrameShape(QFrame.Shape.HLine)
        main_layout.addWidget(self.divisor)

        # Scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent; border: none;")

        scroll_content = QWidget()
        scroll_content.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        scroll_content.setStyleSheet("background: transparent; border: none;")
        menu_layout = QVBoxLayout(scroll_content)
        menu_layout.setContentsMargins(0, 6, 0, 0)
        menu_layout.setSpacing(2)

        # Seção Principal
        first_btn = self._add_nav_btn(menu_layout, "Início", "home")
        self._add_nav_btn(menu_layout, "Navegador", "globe")
        self._add_nav_btn(menu_layout, "Downloads", "download")
        self._add_nav_btn(menu_layout, "Biblioteca", "folder")
        self._add_nav_btn(menu_layout, "Favoritos", "star")
        self._add_nav_btn(menu_layout, "Histórico", "clock")

        # Conectores
        self._add_section_label(menu_layout, "CONECTORES")
        self._add_nav_btn(menu_layout, "YouTube", "youtube")
        self._add_nav_btn(menu_layout, "TikTok", "tiktok")
        self._add_nav_btn(menu_layout, "Kiwify", "kiwify")
        self._add_nav_btn(menu_layout, "Hotmart", "hotmart")
        self._add_nav_btn(menu_layout, "Greenn Club", "greenn")
        self._add_nav_btn(menu_layout, "Vimeo", "vimeo")
        self._add_nav_btn(menu_layout, "Google Drive", "drive")
        self._add_nav_btn(menu_layout, "Mega", "mega")
        self._add_nav_btn(menu_layout, "Universo Técnico", "universo")
        self._add_nav_btn(menu_layout, "Chip 7", "chip7")

        # Ferramentas
        self._add_section_label(menu_layout, "FERRAMENTAS")
        self._add_nav_btn(menu_layout, "Configurações", "settings")
        self._add_nav_btn(menu_layout, "Licença", "lock")
        self._add_nav_btn(menu_layout, "Atualizações", "refresh")
        self._add_nav_btn(menu_layout, "Plugins", "plugin")

        menu_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        # Rodapé
        self.footer_label = QLabel("PRT Labs v1.0.0")
        self.footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.footer_label)

        self.aplicar_tema()

        if first_btn:
            self._set_active_button(first_btn)

    def _add_section_label(self, layout: QVBoxLayout, text: str) -> None:
        lbl = QLabel(text)
        self._secoes.append(lbl)
        layout.addWidget(lbl)

    def aplicar_tema(self) -> None:
        """Repinta a barra lateral com a paleta atual."""
        self.setStyleSheet(
            f"background-color: {ThemeColors.SIDEBAR_BG}; border-right: 1px solid {ThemeColors.SIDEBAR_BORDER};"
        )
        self.logo_box.setStyleSheet(
            f"background-color: {ThemeColors.SIDEBAR_LOGO_BG}; "
            f"border: 1px solid {ThemeColors.SIDEBAR_LOGO_BORDER}; border-radius: 10px;"
        )
        self.lbl_title.setStyleSheet(
            f"font-size: 15px; font-weight: 700; color: {ThemeColors.SIDEBAR_TITLE}; background: transparent; border: none;"
        )
        self.lbl_subtitle.setStyleSheet(
            f"font-size: 9px; font-weight: 700; color: {ThemeColors.SIDEBAR_ACCENT}; "
            "letter-spacing: 0.2px; background: transparent; border: none;"
        )
        self.divisor.setStyleSheet(
            f"background-color: {ThemeColors.SIDEBAR_BORDER}; max-height: 1px; border: none;"
        )
        self.footer_label.setStyleSheet(
            f"font-size: 10px; font-weight: 500; color: {ThemeColors.SIDEBAR_MUTED}; "
            "padding: 4px; background: transparent; border: none;"
        )
        for rotulo in self._secoes:
            rotulo.setStyleSheet(
                f"font-size: 10px; font-weight: 700; color: {ThemeColors.SIDEBAR_MUTED}; "
                "margin-top: 14px; margin-bottom: 4px; margin-left: 8px; "
                "background: transparent; border: none; letter-spacing: 0.5px;"
            )
        for botao in self.buttons:
            if botao is self._ativo:
                self._apply_active_style(botao)
            else:
                self._apply_normal_style(botao)

    def _add_nav_btn(self, layout: QVBoxLayout, text: str, icon_key: str) -> QPushButton:
        btn = QPushButton(f"  {text}")
        if icon_key in SVG_ICONS:
            btn.setIcon(svg_to_icon(SVG_ICONS[icon_key], 18))
            btn.setIconSize(QSize(18, 18))

        btn.setProperty("route_name", text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        btn.clicked.connect(lambda: self._on_button_clicked(btn))
        layout.addWidget(btn)
        self.buttons.append(btn)
        self._apply_normal_style(btn)
        return btn

    def selecionar_rota(self, route_name: str) -> None:
        for btn in self.buttons:
            if btn.property("route_name") == route_name:
                self._set_active_button(btn)
                return

    def _on_button_clicked(self, clicked_btn: QPushButton) -> None:
        self._set_active_button(clicked_btn)
        route_name = clicked_btn.property("route_name") or clicked_btn.text().strip()
        self.navigate_requested.emit(route_name)
        self.navigation_requested.emit(route_name)

    def _set_active_button(self, active_btn: QPushButton) -> None:
        self._ativo = active_btn
        for btn in self.buttons:
            if btn == active_btn:
                self._apply_active_style(btn)
            else:
                self._apply_normal_style(btn)

    def _apply_active_style(self, btn: QPushButton) -> None:
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ThemeColors.SIDEBAR_ACTIVE_BG};
                color: {ThemeColors.TEXT};
                border: none;
                border-left: 3px solid {ThemeColors.SIDEBAR_ACCENT};
                border-radius: 0px 6px 6px 0px;
                padding: 7px 10px;
                text-align: left;
                font-size: 13px;
                font-weight: 600;
                outline: none;
            }}
        """)

    def _apply_normal_style(self, btn: QPushButton) -> None:
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {ThemeColors.SIDEBAR_TEXT};
                border: none;
                border-left: 3px solid transparent;
                border-radius: 0px 6px 6px 0px;
                padding: 7px 10px;
                text-align: left;
                font-size: 13px;
                font-weight: 500;
                outline: none;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.SIDEBAR_HOVER_BG};
                color: {ThemeColors.SIDEBAR_HOVER_TEXT};
            }}
        """)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PRT-Nexus")
        self.resize(1280, 720)
        self._ficar_na_bandeja = db_manager.get_setting("bandeja", "0") == "1"
        self.tray: QSystemTrayIcon | None = None
        self._menu_bandeja: QMenu | None = None
        self._aviso: QFrame | None = None

        self._setup_ui()
        if self._ficar_na_bandeja:
            self._garantir_bandeja()
            app = QApplication.instance()
            if app is not None:
                app.setQuitOnLastWindowClosed(False)

    def _setup_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Sidebar Visual Integrada
        self.sidebar = PRTSidebar()
        self.sidebar.navigation_requested.connect(self._on_navigation_requested)

        # 2. QStackedWidget
        self.stacked_widget = QStackedWidget()

        # Instância das Views
        self.home_view = HomeView()
        self.home_view.navigate_requested.connect(self._on_navigation_requested)
        self.browser_view = BrowserView()
        self.downloads_view = DownloadsView()
        self.library_view = LibraryView()
        self.favorites_view = FavoritesView()
        self.history_view = HistoryView()
        self.browser_view.send_to_downloader.connect(self._baixar_do_navegador)
        self.browser_view.favorito_pedido.connect(self._salvar_favorito)
        self.browser_view.pagina_visitada.connect(self._registrar_navegacao)
        self.favorites_view.open_in_browser.connect(self._abrir_no_navegador)
        self.history_view.open_in_browser.connect(self._abrir_no_navegador)
        self.settings_view = SettingsView()
        self.settings_view.tema_mudou.connect(self.sincronizar_tema)
        self.settings_view.chk_bandeja.toggled.connect(self.definir_bandeja)
        self.license_view = LicenseView()
        self.kiwify_view = KiwifyView()
        self.universo_view = UniversoView(downloads_view=self.downloads_view)
        self.chip7_view = Chip7View(downloads_view=self.downloads_view)
        self.mega_view = MegaView(downloads_view=self.downloads_view)
        self.drive_view = DriveView(downloads_view=self.downloads_view)
        self.hotmart_view = HotmartView(downloads_view=self.downloads_view)
        self.greenn_view = GreennView(downloads_view=self.downloads_view)
        self.youtube_view = YouTubeView(downloads_view=self.downloads_view)
        self.tiktok_view = TikTokView(downloads_view=self.downloads_view)
        self.vimeo_view = VimeoView(downloads_view=self.downloads_view)

        # Adiciona as Views ao StackedWidget
        self.stacked_widget.addWidget(self.home_view)
        self.stacked_widget.addWidget(self.browser_view)
        self.stacked_widget.addWidget(self.downloads_view)
        self.stacked_widget.addWidget(self.library_view)
        self.stacked_widget.addWidget(self.favorites_view)
        self.stacked_widget.addWidget(self.history_view)
        self.stacked_widget.addWidget(self.settings_view)
        self.stacked_widget.addWidget(self.license_view)
        self.stacked_widget.addWidget(self.kiwify_view)
        self.stacked_widget.addWidget(self.universo_view)
        self.stacked_widget.addWidget(self.chip7_view)
        self.stacked_widget.addWidget(self.mega_view)
        self.stacked_widget.addWidget(self.drive_view)
        self.stacked_widget.addWidget(self.hotmart_view)
        self.stacked_widget.addWidget(self.greenn_view)
        self.stacked_widget.addWidget(self.youtube_view)
        self.stacked_widget.addWidget(self.tiktok_view)
        self.stacked_widget.addWidget(self.vimeo_view)

        # Layout Principal
        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.stacked_widget)
        self.sincronizar_tema()

    def _on_navigation_requested(self, route_name: str) -> None:
        """Alterna a view exibida com base no botão clicado na barra lateral."""
        routes = {
            "Início": self.home_view,
            "Navegador": self.browser_view,
            "Downloads": self.downloads_view,
            "Biblioteca": self.library_view,
            "Favoritos": self.favorites_view,
            "Histórico": self.history_view,
            "Configurações": self.settings_view,
            "Licença": self.license_view,
            "Kiwify": self.kiwify_view,
            "Universo Técnico": self.universo_view,
            "Chip 7": self.chip7_view,
            "Mega": self.mega_view,
            "Google Drive": self.drive_view,
            "Hotmart": self.hotmart_view,
            "Greenn Club": self.greenn_view,
            "YouTube": self.youtube_view,
            "TikTok": self.tiktok_view,
            "Vimeo": self.vimeo_view,
        }

        if route_name in routes:
            self.stacked_widget.setCurrentWidget(routes[route_name])
            self.sidebar.selecionar_rota(route_name)

    def _baixar_do_navegador(self, url: str, pasta: str) -> None:
        self.downloads_view.add_url_to_queue(url, pasta or "Navegador")
        self._on_navigation_requested("Downloads")

    def _salvar_favorito(self, titulo: str, url: str) -> None:
        ok, aviso = self.favorites_view.adicionar(url, titulo, "Navegador")
        if ok:
            QMessageBox.information(self, "Favoritos", "Página salva. Ela aparece em Favoritos.")
            return
        QMessageBox.information(self, "Favoritos", aviso)

    def _registrar_navegacao(self, titulo: str, url: str) -> None:
        db_manager.add_history(titulo, url, plataforma_da_url(url), "Navegação")

    def _abrir_no_navegador(self, url: str) -> None:
        self.browser_view.load_url(url)
        self._on_navigation_requested("Navegador")

    def sincronizar_tema(self) -> None:
        """Ajusta a moldura da janela depois que a paleta muda."""
        self.sidebar.aplicar_tema()
        self.browser_view.atualizar_icones()
        self.settings_view.pintar()
        self.license_view.pintar()
        self.stacked_widget.setObjectName("paginas")
        self.setStyleSheet(
            f"QMainWindow {{ background-color: {ThemeColors.BACKGROUND}; color: {ThemeColors.TEXT}; }}"
        )
        self.stacked_widget.setStyleSheet(
            f"QStackedWidget#paginas {{ background-color: {ThemeColors.BACKGROUND}; }}"
        )

    def definir_bandeja(self, ativo: bool) -> None:
        self._ficar_na_bandeja = ativo
        db_manager.set_setting("bandeja", "1" if ativo else "0")
        app = QApplication.instance()
        if ativo:
            self._garantir_bandeja()
            if app is not None:
                app.setQuitOnLastWindowClosed(False)
            return
        if app is not None:
            app.setQuitOnLastWindowClosed(True)

    def _garantir_bandeja(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        if self.tray is None:
            self.tray = QSystemTrayIcon(svg_to_icon(SVG_ICONS["bolt"], 32), self)
            self.tray.setToolTip("PRT Nexus")
            menu = QMenu()
            abrir = menu.addAction("Abrir")
            abrir.triggered.connect(self._mostrar_de_novo)
            sair = menu.addAction("Sair")
            sair.triggered.connect(self._sair_de_vez)
            self.tray.setContextMenu(menu)
            self.tray.activated.connect(self._bandeja_clicada)
            self._menu_bandeja = menu
        self.tray.show()

    def _bandeja_clicada(self, motivo: QSystemTrayIcon.ActivationReason) -> None:
        if motivo == QSystemTrayIcon.ActivationReason.Trigger:
            self._mostrar_de_novo()

    def _mostrar_de_novo(self) -> None:
        self._fechar_aviso()
        self.showMaximized()
        self.raise_()
        self.activateWindow()

    def _sair_de_vez(self) -> None:
        self._ficar_na_bandeja = False
        QTimer.singleShot(0, self._encerrar)

    def _encerrar(self) -> None:
        self._ficar_na_bandeja = False
        self._fechar_aviso()
        if self.tray is not None:
            self.tray.hide()
        app = QApplication.instance()
        if app is not None:
            app.setQuitOnLastWindowClosed(True)
            app.quit()

    def _fechar_aviso(self) -> None:
        if self._aviso is not None:
            self._aviso.close()
            self._aviso = None

    def _avisar_na_bandeja(self) -> None:
        """Aviso no canto do relógio, com a janela principal já escondida."""
        if not self.isHidden():
            return
        self._fechar_aviso()

        aviso = QFrame()
        aviso.setObjectName("avisoBandeja")
        aviso.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        aviso.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        aviso.setFixedWidth(340)
        aviso.setStyleSheet(f"""
            QFrame#avisoBandeja {{
                background-color: {ThemeColors.CARD};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 10px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        caixa = QVBoxLayout(aviso)
        caixa.setContentsMargins(14, 12, 14, 12)
        caixa.setSpacing(4)

        titulo = QLabel("PRT Nexus")
        titulo.setStyleSheet(f"color: {ThemeColors.TEXT}; font-size: 13px; font-weight: 700;")
        texto = QLabel(
            "O aplicativo continua rodando na bandeja.\n"
            "Clique no ícone ao lado do relógio para abrir de novo."
        )
        texto.setWordWrap(True)
        texto.setStyleSheet(f"color: {ThemeColors.TEXT_SECONDARY}; font-size: 12px;")
        caixa.addWidget(titulo)
        caixa.addWidget(texto)
        aviso.adjustSize()
        aviso.mousePressEvent = lambda _evento: aviso.close()

        tela = QGuiApplication.primaryScreen()
        if tela is not None:
            area = tela.availableGeometry()
            aviso.move(area.right() - aviso.width() - 16, area.bottom() - aviso.height() - 16)
        aviso.show()
        self._aviso = aviso
        QTimer.singleShot(5000, self._fechar_aviso)

    def closeEvent(self, event) -> None:
        if self._ficar_na_bandeja and self.tray is not None and self.tray.isVisible():
            event.ignore()
            self.hide()
            QTimer.singleShot(200, self._avisar_na_bandeja)
            return
        super().closeEvent(event)