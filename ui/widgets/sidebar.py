"""
===========================================================
PRT Nexus - Sidebar Widget
Class: PRTSidebar
Description: Barra lateral de navegação com suporte a ícones/emojis e roteamento seguro.
===========================================================
"""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from theme.colors import ThemeColors

try:
    from theme.icons import get_icon
except ImportError:
    get_icon = None


class PRTSidebar(QWidget):
    """Navegação lateral da aplicação."""

    navigate_requested = Signal(str)
    navigation_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(195)
        self.buttons: list[QPushButton] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 12, 8, 12)
        main_layout.setSpacing(8)

        # Cabeçalho / Logo
        header_container = QWidget()
        header_container.setStyleSheet("background: transparent; border: none;")
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        header_layout.addStretch()

        icon_label = QLabel("⚡")
        icon_label.setStyleSheet("font-size: 18px; color: #F59E0B; background: transparent; border: none;")
        header_layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        titles_layout = QVBoxLayout()
        titles_layout.setContentsMargins(0, 0, 0, 0)
        titles_layout.setSpacing(1)

        lbl_title = QLabel("PRT Nexus")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_title.setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {ThemeColors.TEXT}; background: transparent; border: none;"
        )

        lbl_subtitle = QLabel("Ultra Downloader")
        lbl_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_subtitle.setStyleSheet(
            "font-size: 11px; font-weight: bold; color: #FFFFFF; background: transparent; border: none;"
        )

        titles_layout.addWidget(lbl_title)
        titles_layout.addWidget(lbl_subtitle)

        header_layout.addLayout(titles_layout)
        header_layout.addStretch()

        main_layout.addWidget(header_container)

        # Menu Rolável
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent; border: none;")
        menu_layout = QVBoxLayout(scroll_content)
        menu_layout.setContentsMargins(0, 0, 0, 0)
        menu_layout.setSpacing(3)

        # Seção Principal
        first_btn = self._add_nav_btn(menu_layout, "Início", "home", "🏠")
        self._add_nav_btn(menu_layout, "Navegador", "globe", "🌐")
        self._add_nav_btn(menu_layout, "Downloads", "download", "📥")
        self._add_nav_btn(menu_layout, "Biblioteca", "folder", "📁")
        self._add_nav_btn(menu_layout, "Favoritos", "star", "⭐")
        self._add_nav_btn(menu_layout, "Histórico", "clock", "🕒")

        # Conectores
        self._add_section_label(menu_layout, "CONECTORES")
        self._add_nav_btn(menu_layout, "YouTube", "youtube", "▶")
        self._add_nav_btn(menu_layout, "TikTok", "tiktok", "🎵")
        self._add_nav_btn(menu_layout, "Kiwify", "kiwify", "💚")
        self._add_nav_btn(menu_layout, "Hotmart", "hotmart", "🔥")
        self._add_nav_btn(menu_layout, "Vimeo", "vimeo", "🔷")
        self._add_nav_btn(menu_layout, "Google Drive", "", "📁")
        self._add_nav_btn(menu_layout, "Mega", "", "☁")
        self._add_nav_btn(menu_layout, "Universo Técnico", "", "🌐")
        self._add_nav_btn(menu_layout, "Chip 7", "", "💻")

        # Ferramentas
        self._add_section_label(menu_layout, "FERRAMENTAS")
        self._add_nav_btn(menu_layout, "Configurações", "settings", "⚙")
        self._add_nav_btn(menu_layout, "Licença", "lock", "🔒")
        self._add_nav_btn(menu_layout, "Atualizações", "refresh", "🔄")
        self._add_nav_btn(menu_layout, "Plugins", "plugin", "🧩")

        menu_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        # Rodapé
        footer_label = QLabel("PRT Labs v1.0.0")
        footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer_label.setStyleSheet(
            f"font-size: 10px; color: {ThemeColors.TEXT_SECONDARY}; padding: 2px; background: transparent; border: none;"
        )
        main_layout.addWidget(footer_label)

        self.setStyleSheet(
            f"background-color: {ThemeColors.CARD}; border-right: 1px solid {ThemeColors.BORDER};"
        )

        if first_btn:
            self._set_active_button(first_btn)

    def _add_section_label(self, layout: QVBoxLayout, text: str) -> None:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"font-size: 10px; font-weight: bold; color: {ThemeColors.TEXT_SECONDARY}; "
            f"margin-top: 6px; margin-bottom: 2px; margin-left: 4px; background: transparent; border: none;"
        )
        layout.addWidget(lbl)

    def _add_nav_btn(
        self, layout: QVBoxLayout, text: str, icon_name: str = "", fallback_emoji: str = ""
    ) -> QPushButton:
        has_custom_icon = False

        if get_icon and icon_name:
            icon = get_icon(icon_name)
            if icon and not icon.isNull():
                btn = QPushButton(f"  {text}")
                btn.setIcon(icon)
                btn.setIconSize(QSize(16, 16))
                has_custom_icon = True

        if not has_custom_icon:
            btn_text = f"{fallback_emoji}  {text}" if fallback_emoji else text
            btn = QPushButton(btn_text)

        # Armazena o nome da rota original sem emojis
        btn.setProperty("route_name", text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: self._on_button_clicked(btn))
        layout.addWidget(btn)
        self.buttons.append(btn)
        self._apply_normal_style(btn)
        return btn

    def _on_button_clicked(self, clicked_btn: QPushButton) -> None:
        self._set_active_button(clicked_btn)
        # Recupera a rota limpa armazenada na propriedade
        route_name = clicked_btn.property("route_name") or clicked_btn.text().strip()
        self.navigate_requested.emit(route_name)
        self.navigation_requested.emit(route_name)

    def _set_active_button(self, active_btn: QPushButton) -> None:
        for btn in self.buttons:
            if btn == active_btn:
                self._apply_active_style(btn)
            else:
                self._apply_normal_style(btn)

    def _apply_active_style(self, btn: QPushButton) -> None:
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ThemeColors.PRIMARY};
                color: #FFFFFF;
                border: 1px solid {ThemeColors.PRIMARY};
                border-radius: 6px;
                padding: 6px 8px;
                text-align: left;
                font-size: 12px;
                font-weight: bold;
                outline: none;
            }}
        """)

    def _apply_normal_style(self, btn: QPushButton) -> None:
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {ThemeColors.TEXT};
                border: 1px solid transparent;
                border-radius: 6px;
                padding: 6px 8px;
                text-align: left;
                font-size: 12px;
                outline: none;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.BACKGROUND};
                border-color: {ThemeColors.BORDER};
            }}
        """)