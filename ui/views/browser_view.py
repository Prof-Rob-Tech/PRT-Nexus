"""
===========================================================
PRT Nexus - Browser View
Class: BrowserView
Description: Navegador embutido com interceptador inteligente
             e extrator de módulos/aulas do Kiwify.
===========================================================
"""
from PySide6.QtCore import QUrl, Signal, Slot
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtWebEngineCore import QWebEngineUrlRequestInterceptor
from PySide6.QtWebEngineWidgets import QWebEngineView

from theme.colors import ThemeColors


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

        self.btn_back = QPushButton("◄")
        self.btn_forward = QPushButton("►")
        self.btn_reload = QPushButton("🔄")

        for btn in (self.btn_back, self.btn_forward, self.btn_reload):
            btn.setFixedSize(32, 32)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {ThemeColors.CARD};
                    color: {ThemeColors.TEXT};
                    border: 1px solid {ThemeColors.BORDER};
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    background-color: {ThemeColors.BACKGROUND};
                }}
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

        # Botão para capturar a lista de aulas (DIA 01, DIA 02...)
        self.btn_extract_kiwify = QPushButton("📦 Extrair Aulas da Página")
        self.btn_extract_kiwify.setFixedHeight(34)
        self.btn_extract_kiwify.setStyleSheet("""
            QPushButton {
                background-color: #00B563;
                color: #FFFFFF;
                border-radius: 4px;
                padding: 0 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #009652;
            }
        """)
        self.btn_extract_kiwify.clicked.connect(self.extract_kiwify_structure)

        self.btn_media_count = QPushButton("🎬 Mídias (0)")
        self.btn_media_count.setFixedHeight(34)
        self.btn_media_count.setStyleSheet(f"""
            QPushButton {{
                background-color: {ThemeColors.CARD};
                color: {ThemeColors.PRIMARY};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 4px;
                padding: 0 12px;
                font-weight: bold;
            }}
        """)
        
        self.btn_media_count.clicked.connect(self.show_media_dialog)

        nav_bar.addWidget(self.btn_back)
        nav_bar.addWidget(self.btn_forward)
        nav_bar.addWidget(self.btn_reload)
        nav_bar.addWidget(self.url_bar, stretch=1)
        nav_bar.addWidget(self.btn_go)
        nav_bar.addWidget(self.btn_extract_kiwify)
        nav_bar.addWidget(self.btn_media_count)

        layout.addLayout(nav_bar)

        # Componente WebEngine
        self.web_view = QWebEngineView()
        
        # Interceptador de URLs
        self.interceptor = MediaUrlInterceptor(self._on_media_detected)
        self.web_view.page().profile().setUrlRequestInterceptor(self.interceptor)

        self.web_view.urlChanged.connect(self.update_url_bar)
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
        self.url_bar.setText(qurl.toString())

    def _on_media_detected(self, media_url: str) -> None:
        if media_url not in self.detected_media:
            self.detected_media.append(media_url)
            self.btn_media_count.setText(f"🎬 Mídias ({len(self.detected_media)})")

    def extract_kiwify_structure(self) -> None:
        """Executa um script JS no navegador para extrair Módulos (DIA 01) e Aulas (BLOCO 01..07)."""
        js_script = """
        (function() {
            let items = [];
            let currentModule = "DIA 01";
            
            // Procura os títulos dos módulos e das aulas no DOM da Kiwify
            let elements = document.querySelectorAll('div, span, p, a');
            elements.forEach(el => {
                let text = el.innerText ? el.innerText.trim() : "";
                if (/^DIA\\s+\\d+/i.test(text) && text.length < 15) {
                    currentModule = text;
                } else if (/^BLOCO\\s+\\d+/i.test(text) && text.length < 20) {
                    items.push({
                        module: currentModule,
                        lesson: text,
                        url: window.location.href
                    });
                }
            });
            
            // Remove duplicados
            let uniqueItems = list => Array.from(new Set(list.map(a => JSON.stringify(a)))).map(a => JSON.parse(a));
            return uniqueItems(items);
        })();
        """
        self.web_view.page().runJavaScript(js_script, self._on_kiwify_extracted)

    def _on_kiwify_extracted(self, result) -> None:
        if not result or len(result) == 0:
            QMessageBox.information(
                self, 
                "Aviso", 
                "Nenhuma estrutura de aula detetada nesta página. Certifique-se de que a barra lateral com as aulas está visível."
            )
            return

        count = 0
        for item in result:
            mod_folder = item.get("module", "DIA 01")
            lesson_title = item.get("lesson", "Aula")
            page_url = item.get("url", self.web_view.url().toString())
            
            # Envia a URL com a indicação da subpasta (ex: "Kiwify/DIA 01")
            subfolder = f"Kiwify/{mod_folder}"
            self.send_to_downloader.emit(page_url, subfolder)
            count += 1

        QMessageBox.information(
            self, 
            "Sucesso", 
            f"Foram enviadas {count} aulas (Módulos e Blocos) para o Gerenciador de Downloads!"
        )

    def show_media_dialog(self) -> None:
        if not self.detected_media:
            QMessageBox.information(self, "Mídias", "Nenhum stream de vídeo válido capturado até ao momento.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Mídias de Vídeo Encontradas")
        dialog.setFixedSize(650, 350)
        
        dlg_layout = QVBoxLayout(dialog)
        list_widget = QListWidget()
        list_widget.addItems(self.detected_media)
        dlg_layout.addWidget(list_widget)

        btn_send = QPushButton("Enviar Link Selecionado para Downloads")
        btn_send.clicked.connect(lambda: self._send_selected_media(list_widget, dialog))
        dlg_layout.addWidget(btn_send)

        dialog.exec()

    def _send_selected_media(self, list_widget: QListWidget, dialog: QDialog) -> None:
        selected_item = list_widget.currentItem()
        if selected_item:
            self.send_to_downloader.emit(selected_item.text(), "Kiwify/DIA 01")
            dialog.accept()
            QMessageBox.information(self, "Sucesso", "Link de vídeo enviado para a fila de downloads!")