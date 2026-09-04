"""
===========================================================
PRT Nexus - History View
Class: HistoryView
Description: Interface para visualização e gerenciamento do histórico de atividades.
===========================================================
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from theme.colors import ThemeColors

try:
    from database.manager import db_manager
except ImportError:
    db_manager = None


class HistoryView(QWidget):
    """Interface para exibição e pesquisa do histórico de navegação e downloads."""

    open_in_browser = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._history_data: list = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # Cabeçalho
        header_layout = QHBoxLayout()

        title_layout = QVBoxLayout()
        title_layout.setSpacing(4)

        lbl_title = QLabel("📜 Histórico de Atividades")
        lbl_title.setStyleSheet(
            f"font-size: 20px; font-weight: bold; color: {ThemeColors.TEXT}; background: transparent;"
        )

        lbl_subtitle = QLabel("Registro de links acessados, downloads executados e mídias interceptadas.")
        lbl_subtitle.setStyleSheet(
            f"font-size: 13px; color: {ThemeColors.TEXT_SECONDARY}; background: transparent;"
        )

        title_layout.addWidget(lbl_title)
        title_layout.addWidget(lbl_subtitle)
        header_layout.addLayout(title_layout, stretch=1)

        # Botão de Limpar
        self.btn_clear = QPushButton("🗑️ Limpar Histórico")
        self.btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {ThemeColors.TEXT_SECONDARY};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
                padding: 8px 14px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                border-color: #EF4444;
                color: #EF4444;
            }}
        """)
        self.btn_clear.clicked.connect(self._clear_history)
        header_layout.addWidget(self.btn_clear)

        main_layout.addLayout(header_layout)

        # Barra de Pesquisa
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍  Pesquisar no histórico...")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {ThemeColors.CARD};
                color: {ThemeColors.TEXT};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {ThemeColors.PRIMARY};
            }}
        """)
        self.search_input.textChanged.connect(self._filter_history)
        main_layout.addWidget(self.search_input)

        # Container Principal
        self.container_frame = QFrame()
        self.container_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {ThemeColors.CARD};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
            }}
        """)

        self.container_layout = QVBoxLayout(self.container_frame)
        self.container_layout.setContentsMargins(20, 20, 20, 20)

        # Estado Vazio
        self.empty_widget = QWidget()
        self.empty_widget.setStyleSheet("background: transparent; border: none;")
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(10)

        lbl_empty_icon = QLabel("📜")
        lbl_empty_icon.setStyleSheet("font-size: 48px; background: transparent; border: none;")
        lbl_empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_empty_title = QLabel("Histórico vazio")
        lbl_empty_title.setStyleSheet(f"""
            font-size: 16px;
            font-weight: bold;
            color: {ThemeColors.TEXT};
            background: transparent;
            border: none;
        """)
        lbl_empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_empty_desc = QLabel(
            "Nenhuma atividade recente foi registrada. Seus acessos e downloads aparecerão aqui automaticamente."
        )
        lbl_empty_desc.setStyleSheet(f"""
            font-size: 13px;
            color: {ThemeColors.TEXT_SECONDARY};
            background: transparent;
            border: none;
        """)
        lbl_empty_desc.setWordWrap(True)
        lbl_empty_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_empty_desc.setMaximumWidth(520)

        empty_layout.addStretch()
        empty_layout.addWidget(lbl_empty_icon)
        empty_layout.addWidget(lbl_empty_title)
        empty_layout.addWidget(lbl_empty_desc)
        empty_layout.addStretch()

        self.container_layout.addWidget(self.empty_widget)

        # Scroll Area para os Cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("border: none; background: transparent;")

        self.cards_container = QWidget()
        self.cards_container.setStyleSheet("background: transparent;")
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setSpacing(10)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.cards_container)
        self.container_layout.addWidget(self.scroll_area)
        self.scroll_area.setVisible(False)

        main_layout.addWidget(self.container_frame, stretch=1)
        self.load_history()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.load_history()

    def load_history(self) -> None:
        if db_manager and hasattr(db_manager, "get_all_history"):
            try:
                self._history_data = db_manager.get_all_history() or []
            except Exception:
                self._history_data = []

        self._render_history(self._history_data)

    def _filter_history(self, text: str) -> None:
        query = text.strip().lower()
        if not query:
            self._render_history(self._history_data)
            return

        filtered = [
            item for item in self._history_data
            if query in str(item.get("title", "")).lower()
            or query in str(item.get("url", "")).lower()
            or query in str(item.get("platform", "")).lower()
            or query in str(item.get("action_type", "")).lower()
        ]
        self._render_history(filtered)

    def _render_history(self, items: list) -> None:
        while self.cards_layout.count():
            child = self.cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not items:
            self.empty_widget.setVisible(True)
            self.scroll_area.setVisible(False)
            return

        self.empty_widget.setVisible(False)
        self.scroll_area.setVisible(True)

        for item in items:
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {ThemeColors.BACKGROUND};
                    border: 1px solid {ThemeColors.BORDER};
                    border-radius: 6px;
                    padding: 8px;
                }}
            """)
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(12, 8, 12, 8)

            title = item.get("title") or "Página sem título"
            url = item.get("url", "")
            platform = item.get("platform", "Geral")
            action = item.get("action_type", "Acesso")
            created_at = item.get("created_at", "")

            info_layout = QVBoxLayout()
            info_layout.setSpacing(2)

            lbl_title = QLabel(f"🌐 {title}")
            lbl_title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {ThemeColors.TEXT}; border: none;")

            lbl_meta = QLabel(f"{platform.upper()} • {action.upper()} • {created_at}\n{url}")
            lbl_meta.setStyleSheet(f"font-size: 12px; color: {ThemeColors.TEXT_SECONDARY}; border: none;")

            info_layout.addWidget(lbl_title)
            info_layout.addWidget(lbl_meta)
            card_layout.addLayout(info_layout, stretch=1)

            if url:
                btn_open = QPushButton("▶ Abrir")
                btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_open.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {ThemeColors.PRIMARY};
                        color: white;
                        border: none;
                        border-radius: 4px;
                        padding: 6px 12px;
                        font-weight: bold;
                    }}
                """)
                btn_open.clicked.connect(lambda _, u=url: self.open_in_browser.emit(u))
                card_layout.addWidget(btn_open)

            self.cards_layout.addWidget(card)

    def _clear_history(self) -> None:
        if not self._history_data:
            return

        reply = QMessageBox.question(
            self,
            "Limpar Histórico",
            "Tem certeza que deseja apagar todo o histórico de atividades?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            if db_manager and hasattr(db_manager, "clear_history"):
                db_manager.clear_history()
                self.load_history()