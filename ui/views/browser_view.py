"""
===========================================================
PRT Nexus - Browser View
Class: BrowserView
Description: Navegador embutido com interceptador inteligente
             e extrator de módulos/aulas do Kiwify.
===========================================================
"""
from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtWebEngineCore import QWebEngineUrlRequestInterceptor
from PySide6.QtWebEngineWidgets import QWebEngineView

from theme.colors import ThemeColors


def _icone(svg: str, tamanho: int = 16) -> QIcon:
    renderer = QSvgRenderer(bytes(svg, "utf-8"))
    pixmap = QPixmap(tamanho, tamanho)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


_SETA_VOLTAR = '<svg viewBox="0 0 24 24" fill="none" stroke="#E4E4E7" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>'
_SETA_AVANCAR = '<svg viewBox="0 0 24 24" fill="none" stroke="#E4E4E7" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>'
_RECARREGAR = '<svg viewBox="0 0 24 24" fill="none" stroke="#E4E4E7" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.5 15a9 9 0 1 1-2.1-9.4L23 10"/></svg>'


class MediaUrlInterceptor(QWebEngineUrlRequestInterceptor):
    """Intercepta apenas pedidos diretos de streaming de vídeo (m3u8, mp4, panda, vimeo)."""

    def __init__(self, callback) -> None:
        super().__init__()
        self.callback = callback
        # Extensões e padrões válidos de vídeo
        self.valid_patterns = [".m3u8", ".mp4", "pandavideo.com", "vdocipher", "player.vimeo.com/video"]

    def interceptRequest(self, info) -> None:
        url = info.requestUrl().toString()
        url_lower = url.lower()
        
        # Ignora URLs da própria interface/dashboard da Kiwify
        if "dashboard.kiwify.com" in url_lower or "members.kiwify.com.br" in url_lower:
            if not any(ext in url_lower for ext in [".mp4", ".m3u8"]):
                return

        if any(pattern in url_lower for pattern in self.valid_patterns):
            self.callback(url)


class BrowserView(QWidget):
    """Visualizador de Navegador Web Integrado."""

    send_to_downloader = Signal(str, str)  # (url, subfolder)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.detected_media = []
        self.setup_ui()

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Barra de Navegação Superior
        nav_bar = QHBoxLayout()
        nav_bar.setContentsMargins(10, 8, 10, 8)
        nav_bar.setSpacing(8)

        self.btn_back = QPushButton()
        self.btn_forward = QPushButton()
        self.btn_reload = QPushButton()
        self.btn_back.setIcon(_icone(_SETA_VOLTAR))
        self.btn_forward.setIcon(_icone(_SETA_AVANCAR))
        self.btn_reload.setIcon(_icone(_RECARREGAR))
        self.btn_back.setToolTip("Voltar")
        self.btn_forward.setToolTip("Avançar")
        self.btn_reload.setToolTip("Recarregar")

        for btn in (self.btn_back, self.btn_forward, self.btn_reload):
            btn.setFixedSize(34, 34)
            btn.setIconSize(QSize(16, 16))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #2A2A2A;
                }
            """)

        self.url_bar = QLineEdit()
        self.url_bar.setFixedHeight(34)
        self.url_bar.setStyleSheet(f"""
            QLineEdit {{
                background-color: {ThemeColors.BACKGROUND};
                color: {ThemeColors.TEXT};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 4px;
                padding: 0 10px;
            }}
        """)
        self.url_bar.returnPressed.connect(self.navigate_to_url)

        self.btn_go = QPushButton("Ir")
        self.btn_go.setFixedHeight(34)
        self.btn_go.setStyleSheet(f"""
            QPushButton {{
                background-color: {ThemeColors.PRIMARY};
                color: #FFFFFF;
                border-radius: 4px;
                padding: 0 14px;
                font-weight: bold;
            }}
        """)
        self.btn_go.clicked.connect(self.navigate_to_url)

        self.btn_baixar = QPushButton("Baixar esse vídeo")
        self.btn_baixar.setFixedHeight(34)
        self.btn_baixar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_baixar.setStyleSheet("""
            QPushButton {
                background-color: #00B563;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 0 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #009652;
            }
        """)
        self.btn_baixar.clicked.connect(self.baixar_pagina_atual)

        self.btn_media_count = QPushButton("Mídias (0)")
        self.btn_media_count.setFixedHeight(34)
        self.btn_media_count.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_media_count.setStyleSheet(f"""
            QPushButton {{
                background-color: {ThemeColors.CARD};
                color: {ThemeColors.TEXT};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
                padding: 0 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #323232;
            }}
        """)
        self.btn_media_count.clicked.connect(self.show_media_dialog)

        nav_bar.addWidget(self.btn_back)
        nav_bar.addWidget(self.btn_forward)
        nav_bar.addWidget(self.btn_reload)
        nav_bar.addWidget(self.url_bar, stretch=1)
        nav_bar.addWidget(self.btn_go)
        nav_bar.addWidget(self.btn_baixar)
        nav_bar.addWidget(self.btn_media_count)

        layout.addLayout(nav_bar)

        self.setAutoFillBackground(True)
        paleta = self.palette()
        paleta.setColor(self.backgroundRole(), QColor(ThemeColors.BACKGROUND))
        self.setPalette(paleta)

        self.web_view = QWebEngineView()
        self.web_view.page().setBackgroundColor(QColor(ThemeColors.BACKGROUND))
        self.web_view.urlChanged.connect(self.update_url_bar)
        self.web_view.setHtml(
            f"<html><body style='background:{ThemeColors.BACKGROUND};margin:0'></body></html>"
        )
        
        # Interceptador de URLs
        self.interceptor = MediaUrlInterceptor(self._on_media_detected)
        self.web_view.page().profile().setUrlRequestInterceptor(self.interceptor)

        self.btn_back.clicked.connect(self.web_view.back)
        self.btn_forward.clicked.connect(self.web_view.forward)
        self.btn_reload.clicked.connect(self.web_view.reload)

        layout.addWidget(self.web_view, stretch=1)

    def load_url(self, url_str: str) -> None:
        """Carrega uma URL no navegador."""
        if not url_str.startswith("http://") and not url_str.startswith("https://"):
            url_str = "https://" + url_str
        self.url_bar.setText(url_str)
        self.web_view.load(QUrl(url_str))

    def navigate_to_url(self) -> None:
        url_text = self.url_bar.text().strip()
        if url_text:
            self.load_url(url_text)

    def update_url_bar(self, qurl: QUrl) -> None:
        texto = qurl.toString()
        if not texto or texto == "about:blank" or texto.startswith("data:"):
            self.url_bar.clear()
            return
        self.url_bar.setText(texto)
        if self._e_pagina_de_video(texto):
            self._on_media_detected(texto)

    def _e_pagina_de_video(self, url: str) -> bool:
        baixa = (url or "").lower()
        marcas = (
            "youtube.com/watch",
            "youtu.be/",
            "vimeo.com/",
            "tiktok.com/",
            "instagram.com/reel",
            "dailymotion.com/video",
        )
        return any(marca in baixa for marca in marcas)

    def _on_media_detected(self, media_url: str) -> None:
        if not media_url or media_url in self.detected_media:
            return
        self.detected_media.append(media_url)
        self.btn_media_count.setText(f"Mídias ({len(self.detected_media)})")

    def baixar_pagina_atual(self) -> None:
        url = self.web_view.url().toString()
        if not url.startswith("http"):
            QMessageBox.information(self, "Navegador", "Abra uma página antes de baixar.")
            return
        self.send_to_downloader.emit(url, "Navegador")

    def show_media_dialog(self) -> None:
        if not self.detected_media:
            QMessageBox.information(
                self,
                "Mídias",
                "Ainda não há vídeo nesta navegação. Abra a página do vídeo e tente de novo.",
            )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Mídias encontradas")
        dialog.setFixedSize(650, 350)
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {ThemeColors.BACKGROUND};
                color: {ThemeColors.TEXT};
            }}
            QListWidget {{
                background-color: {ThemeColors.CARD};
                color: {ThemeColors.TEXT};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
            }}
            QPushButton#btn_enviar {{
                background-color: #00B563;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: bold;
            }}
            QPushButton#btn_limpar {{
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: bold;
            }}
            QPushButton#btn_limpar:hover {{
                background-color: #8b0000;
            }}
        """)
        dlg_layout = QVBoxLayout(dialog)
        list_widget = QListWidget()
        list_widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        list_widget.addItems(self.detected_media)
        dlg_layout.addWidget(list_widget)

        botoes = QHBoxLayout()
        btn_limpar = QPushButton("Limpar links")
        btn_limpar.setObjectName("btn_limpar")
        btn_limpar.clicked.connect(lambda: self._limpar_midias(dialog))
        btn_send = QPushButton("Enviar lista para Downloads")
        btn_send.setObjectName("btn_enviar")
        btn_send.clicked.connect(lambda: self._send_selected_media(list_widget, dialog))
        botoes.addWidget(btn_limpar)
        botoes.addWidget(btn_send, stretch=1)
        dlg_layout.addLayout(botoes)
        dialog.exec()

    def _limpar_midias(self, dialog: QDialog) -> None:
        self.detected_media.clear()
        self.btn_media_count.setText("Mídias (0)")
        dialog.accept()

    def _send_selected_media(self, list_widget: QListWidget, dialog: QDialog) -> None:
        links = [list_widget.item(i).text() for i in range(list_widget.count()) if list_widget.item(i).text()]
        if not links:
            QMessageBox.information(self, "Mídias", "A lista está vazia.")
            return
        for link in links:
            self.send_to_downloader.emit(link, "Navegador")
        dialog.accept()