"""
===========================================================
PRT Nexus - Kiwify View
Class: KiwifyView
Description: Interface visual do Conector Kiwify com suporte a Login integrativo.
===========================================================
"""
from PySide6.QtCore import QByteArray, Qt, Signal
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.extractors.kiwify_connector import KiwifyConnector
from theme.colors import ThemeColors

KIWIFY_SVG = '<svg viewBox="0 0 24 24"><path fill="#00B563" d="M18.8 17.3C17.1 19.5 14.5 20.8 11.6 20.8C6.3 20.8 2 16.5 2 11.2C2 7.7 3.9 4.6 6.8 2.9C7.3 2.6 8 3 8 3.6C8 3.8 7.9 4 7.8 4.2C5.3 5.7 3.8 8.3 3.8 11.2C3.8 15.5 7.3 19 11.6 19C13.9 19 16 18 17.4 16.3C17.7 15.9 18.3 15.9 18.7 16.2C19.1 16.5 19.1 17 18.8 17.3Z"/><ellipse cx="7.2" cy="10.8" rx="0.9" ry="1.8" transform="rotate(-50 7.2 10.8)" fill="#00B563"/><ellipse cx="8.8" cy="13.5" rx="0.9" ry="1.8" transform="rotate(-25 8.8 13.5)" fill="#00B563"/><ellipse cx="11.2" cy="15.2" rx="0.9" ry="1.8" transform="rotate(0 11.2 15.2)" fill="#00B563"/><ellipse cx="14.2" cy="15.8" rx="0.9" ry="1.8" transform="rotate(30 14.2 15.8)" fill="#00B563"/></svg>'


def get_kiwify_pixmap(size: int = 28) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(KIWIFY_SVG.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


class KiwifyView(QWidget):
    """Visualização do Conector Kiwify."""

    send_to_downloader = Signal(str)
    open_login_browser = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.connector = KiwifyConnector()
        self.setup_ui()

    def setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # Header / Título
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        lbl_icon = QLabel()
        lbl_icon.setPixmap(get_kiwify_pixmap(28))

        lbl_title = QLabel("Conector Kiwify")
        lbl_title.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {ThemeColors.TEXT};")

        btn_login = QPushButton("🔑 Fazer Login na Kiwify")
        btn_login.setFixedHeight(34)
        btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_login.setStyleSheet(f"""
            QPushButton {{
                background-color: {ThemeColors.CARD};
                color: {ThemeColors.TEXT};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
                padding: 0 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.BACKGROUND};
                border-color: #00B563;
            }}
        """)
        btn_login.clicked.connect(lambda: self.open_login_browser.emit("https://dashboard.kiwify.com/courses"))

        header_layout.addWidget(lbl_icon)
        header_layout.addWidget(lbl_title)
        header_layout.addStretch()
        header_layout.addWidget(btn_login)

        main_layout.addLayout(header_layout)

        lbl_subtitle = QLabel("Extraia e baixe vídeos e materiais de cursos hospedados na área de membros Kiwify.")
        lbl_subtitle.setStyleSheet(f"font-size: 13px; color: {ThemeColors.TEXT_SECONDARY}; margin-bottom: 8px;")
        main_layout.addWidget(lbl_subtitle)

        # Card de Configuração / URL
        card_frame = QFrame()
        card_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {ThemeColors.CARD};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
            }}
        """)
        card_layout = QVBoxLayout(card_frame)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)

        lbl_url = QLabel("URL da Aula ou Curso Kiwify:")
        lbl_url.setStyleSheet(f"color: {ThemeColors.TEXT}; font-weight: bold; font-size: 12px; border: none;")
        card_layout.addWidget(lbl_url)

        input_layout = QHBoxLayout()
        input_layout.setSpacing(8)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://members.kiwify.com.br/...")
        self.url_input.setFixedHeight(38)
        self.url_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {ThemeColors.BACKGROUND};
                color: {ThemeColors.TEXT};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
                padding: 0 12px;
            }}
        """)
        input_layout.addWidget(self.url_input)

        self.btn_fetch = QPushButton("Analisar Link")
        self.btn_fetch.setFixedHeight(38)
        self.btn_fetch.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_fetch.setStyleSheet("""
            QPushButton {
                background-color: #00B563;
                color: #FFFFFF;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                padding: 0 18px;
            }
            QPushButton:hover {
                background-color: #009652;
            }
        """)
        self.btn_fetch.clicked.connect(self._on_fetch_clicked)
        input_layout.addWidget(self.btn_fetch)

        card_layout.addLayout(input_layout)

        lbl_cookie = QLabel("Cookie de Sessão / Token (Opcional - preenchido automaticamente ao logar):")
        lbl_cookie.setStyleSheet(f"color: {ThemeColors.TEXT_SECONDARY}; font-size: 11px; border: none; padding-top: 4px;")
        card_layout.addWidget(lbl_cookie)

        self.cookie_input = QLineEdit()
        self.cookie_input.setPlaceholderText("Cole o cookie de autenticação caso queira autenticar manualmente...")
        self.cookie_input.setFixedHeight(34)
        self.cookie_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {ThemeColors.BACKGROUND};
                color: {ThemeColors.TEXT_SECONDARY};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
                padding: 0 10px;
                font-size: 12px;
            }}
        """)
        card_layout.addWidget(self.cookie_input)

        main_layout.addWidget(card_frame)

        # Árvore de Módulos e Aulas
        lbl_results = QLabel("Conteúdo Identificado:")
        lbl_results.setStyleSheet(f"font-weight: bold; color: {ThemeColors.TEXT}; font-size: 13px;")
        main_layout.addWidget(lbl_results)

        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Título da Aula / Módulo", "Tipo", "Status"])
        self.tree_widget.setColumnWidth(0, 450)
        self.tree_widget.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {ThemeColors.CARD};
                color: {ThemeColors.TEXT};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
            }}
            QHeaderView::section {{
                background-color: {ThemeColors.BACKGROUND};
                color: {ThemeColors.TEXT};
                padding: 6px;
                border: none;
                font-weight: bold;
            }}
        """)
        main_layout.addWidget(self.tree_widget, stretch=1)

        # Rodapé
        actions_layout = QHBoxLayout()
        actions_layout.addStretch()

        self.btn_download = QPushButton("Enviar Aulas Selecionadas para Downloads")
        self.btn_download.setFixedHeight(40)
        self.btn_download.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_download.setStyleSheet("""
            QPushButton {
                background-color: #00B563;
                color: #FFFFFF;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                padding: 0 20px;
            }
            QPushButton:hover {
                background-color: #009652;
            }
        """)
        self.btn_download.clicked.connect(self._on_download_clicked)
        actions_layout.addWidget(self.btn_download)

        main_layout.addLayout(actions_layout)

    def _on_fetch_clicked(self) -> None:
        url = self.url_input.text().strip()
        cookie = self.cookie_input.text().strip()

        if not url:
            QMessageBox.warning(self, "Aviso", "Por favor, insira a URL da aula ou do curso Kiwify.")
            return

        if cookie:
            self.connector.set_auth_token(cookie)

        info = self.connector.fetch_course_info(url)
        if not info.get("success"):
            QMessageBox.critical(self, "Erro", info.get("error", "Erro ao carregar link."))
            return

        self.tree_widget.clear()
        for mod in info.get("modules", []):
            mod_item = QTreeWidgetItem(self.tree_widget, [mod["module_name"], "Módulo", ""])
            mod_item.setExpanded(True)
            for lesson in mod.get("lessons", []):
                QTreeWidgetItem(mod_item, [lesson["title"], lesson["type"].capitalize(), lesson["status"]])

    def _on_download_clicked(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Aviso", "Nenhum link ativo para baixar.")
            return

        self.send_to_downloader.emit(url)
        QMessageBox.information(self, "Sucesso", "Link enviado para a fila de downloads!")