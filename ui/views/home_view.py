"""
===========================================================
PRT Nexus - Home View (Dashboard)
Class: HomeView
Description: Tela inicial com Ultra Downloader no título principal.
===========================================================
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from theme.colors import ThemeColors


class StatCard(QFrame):
    """Cartão de métrica com indicador colorido no lado esquerdo."""

    def __init__(self, title: str, value: str, bar_color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {ThemeColors.CARD};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 16, 16, 16)
        layout.setSpacing(14)

        color_bar = QFrame()
        color_bar.setFixedWidth(5)
        color_bar.setStyleSheet(f"""
            background-color: {bar_color};
            border-radius: 2px;
            border: none;
        """)
        layout.addWidget(color_bar)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(8)

        lbl_title = QLabel(title.upper())
        lbl_title.setStyleSheet(f"""
            font-size: 11px;
            font-weight: bold;
            color: {ThemeColors.TEXT_SECONDARY};
            border: none;
            background: transparent;
        """)

        lbl_value = QLabel(value)
        lbl_value.setStyleSheet(f"""
            font-size: 15px;
            font-weight: bold;
            color: {ThemeColors.TEXT};
            border: none;
            background: transparent;
        """)

        text_layout.addWidget(lbl_title)
        text_layout.addWidget(lbl_value)
        layout.addLayout(text_layout)


class ShortcutCard(QFrame):
    """Cartão de atalho rápido para cada módulo/conector."""

    clicked = Signal(str)

    def __init__(self, title: str, description: str, route_target: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.route_target = route_target

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {ThemeColors.CARD};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"""
            font-size: 14px;
            font-weight: bold;
            color: {ThemeColors.TEXT};
            border: none;
            background: transparent;
        """)

        lbl_desc = QLabel(description)
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet(f"""
            font-size: 12px;
            color: {ThemeColors.TEXT_SECONDARY};
            border: none;
            background: transparent;
        """)

        btn_access = QPushButton("Acessar Módulo →")
        btn_access.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_access.setStyleSheet(f"""
            QPushButton {{
                background-color: {ThemeColors.BACKGROUND};
                color: {ThemeColors.TEXT};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
                font-weight: bold;
                margin-top: 8px;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.PRIMARY};
                border-color: {ThemeColors.PRIMARY};
                color: #FFFFFF;
            }}
        """)
        btn_access.clicked.connect(lambda: self.clicked.emit(self.route_target))

        layout.addWidget(lbl_title)
        layout.addWidget(lbl_desc)
        layout.addStretch()
        layout.addWidget(btn_access)


class HomeView(QWidget):
    """View principal da Dashboard do PRT Nexus."""

    navigate_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(32, 28, 32, 28)
        container_layout.setSpacing(28)

        # -------------------------------------------------------------
        # CABEÇALHO
        # -------------------------------------------------------------
        header_layout = QVBoxLayout()
        header_layout.setSpacing(6)

        lbl_title = QLabel("PRT Nexus - Ultra Downloader")
        lbl_title.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {ThemeColors.TEXT};")

        lbl_subtitle = QLabel("Central de download, extração de mídias e gestão de conectores.")
        lbl_subtitle.setStyleSheet(f"font-size: 14px; color: {ThemeColors.TEXT_SECONDARY};")

        header_layout.addWidget(lbl_title)
        header_layout.addWidget(lbl_subtitle)
        container_layout.addLayout(header_layout)

        # -------------------------------------------------------------
        # MÉTRICAS
        # -------------------------------------------------------------
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(16)

        card1 = StatCard("Conectores", "9 Módulos Prontos", "#10B981")
        card2 = StatCard("Downloads Ativos", "0 em andamento", "#6366F1")
        card3 = StatCard("Mídias Salvas", "0 arquivos", "#F59E0B")
        card4 = StatCard("Sistema Core", "100% Operacional", "#06B6D4")

        stats_layout.addWidget(card1)
        stats_layout.addWidget(card2)
        stats_layout.addWidget(card3)
        stats_layout.addWidget(card4)

        container_layout.addLayout(stats_layout)

        # -------------------------------------------------------------
        # ATALHOS RÁPIDOS
        # -------------------------------------------------------------
        shortcuts_section = QVBoxLayout()
        shortcuts_section.setSpacing(16)

        lbl_section_title = QLabel("Atalhos Rápidos de Conectores")
        lbl_section_title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {ThemeColors.TEXT};")
        shortcuts_section.addWidget(lbl_section_title)

        grid_layout = QGridLayout()
        grid_layout.setSpacing(16)

        items = [
            ("Navegador Web", "Navegar e extrair URLs direto de sites", "Navegador"),
            ("Downloads", "Ver gerenciador e histórico de downloads", "Downloads"),
            ("YouTube", "Download de vídeos, playlists e áudio", "YouTube"),
            ("TikTok", "Extrair vídeos e Reels sem marca d'água", "TikTok"),
            ("Kiwify", "Acessar conteúdos da plataforma Kiwify", "Kiwify"),
            ("Hotmart", "Acessar áreas de membros da Hotmart", "Hotmart"),
            ("Google Drive", "Baixar arquivos e pastas do Drive", "Google Drive"),
            ("Universo Técnico", "Extrair aulas do Universo Técnico", "Universo Técnico"),
            ("Chip 7", "Acessar cursos e extrair vídeos do Vimeo", "Chip 7"),
        ]

        row, col = 0, 0
        for title, desc, target in items:
            card = ShortcutCard(title, desc, target)
            card.clicked.connect(self._on_shortcut_clicked)
            grid_layout.addWidget(card, row, col)
            col += 1
            if col > 3:
                col = 0
                row += 1

        shortcuts_section.addLayout(grid_layout)
        container_layout.addLayout(shortcuts_section)

        container_layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def _on_shortcut_clicked(self, route_target: str) -> None:
        self.navigate_requested.emit(route_target)