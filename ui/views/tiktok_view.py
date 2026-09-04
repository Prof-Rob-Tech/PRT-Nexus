from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QComboBox, QTableWidget)
from services.extractors.tiktok_connector import TikTokConnector

class TikTokView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Cabeçalho
        title = QLabel("🎵 Conector TikTok")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #FF0050;")
        layout.addWidget(title)

        subtitle = QLabel("Capture e baixe vídeos do TikTok sem marca d'água.")
        subtitle.setStyleSheet("color: #888; margin-bottom: 15px;")
        layout.addWidget(subtitle)

        # Campo de Link
        input_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Cole o link do vídeo do TikTok aqui...")
        
        self.btn_download = QPushButton("Baixar Vídeo")
        self.btn_download.setStyleSheet("background-color: #FF0050; color: white; font-weight: bold;")
        self.btn_download.clicked.connect(self.process_download)

        input_layout.addWidget(self.url_input)
        input_layout.addWidget(self.btn_download)
        layout.addLayout(input_layout)

        layout.addStretch()

    def process_download(self):
        url = self.url_input.text().strip()
        if not url:
            return
        
        connector = TikTokConnector()
        info = connector.get_info(url)
        print("Informações capturadas:", info)