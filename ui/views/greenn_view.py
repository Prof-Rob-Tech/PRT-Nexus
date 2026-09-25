import os

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

VERDE = "#3DDC84"

LOGO_SVG = """
<svg viewBox="0 0 64 76" fill="none">
  <defs>
    <linearGradient id="greennLogo" x1="8" y1="4" x2="56" y2="70" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#D4F562"/>
      <stop offset="0.5" stop-color="#2FDB8A"/>
      <stop offset="1" stop-color="#14C6DE"/>
    </linearGradient>
  </defs>
  <circle cx="32" cy="30" r="19" stroke="url(#greennLogo)" stroke-width="9"/>
  <path fill="url(#greennLogo)" d="M25 47h14l-7 16z"/>
  <path d="M21 31l8 8 15-16" stroke="url(#greennLogo)" stroke-width="5.4" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""


def logo_pixmap(tamanho=36):
    renderer = QSvgRenderer(QByteArray(LOGO_SVG.encode("utf-8")))
    pixmap = QPixmap(tamanho, tamanho)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


class GreennView(QWidget):
    def __init__(self, parent=None, downloads_view=None):
        super().__init__(parent)
        self.downloads_view = downloads_view
        self._montar_interface()
        self._aplicar_estilos()

    def _aplicar_estilos(self):
        self.setStyleSheet(f"""
            QWidget {{ background-color: #101614; color: #ffffff; }}
            QGroupBox {{
                background-color: #101614;
                border: 1px solid #24312b;
                border-radius: 8px;
                margin-top: 4px;
                padding-top: 22px;
                padding-bottom: 8px;
                font-size: 13px;
                font-weight: bold;
                color: #ffffff;
            }}
            QGroupBox::title {{
                subcontrol-origin: padding;
                subcontrol-position: top left;
                left: 10px;
                top: 6px;
                padding: 0 4px;
                background-color: transparent;
                color: #ffffff;
            }}
            QFrame#gb_tabela {{
                background-color: #101614;
                border: 1px solid #24312b;
                border-radius: 12px;
            }}
            QLineEdit, QPlainTextEdit, QComboBox {{
                background-color: #18211d;
                border: 1px solid #2c3d34;
                border-radius: 6px;
                color: #ffffff;
                padding: 6px 10px;
                font-size: 12px;
            }}
            QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{ border: 1px solid {VERDE}; }}
            QLabel.lbl-box {{
                background-color: #18211d;
                border: 1px solid #2c3d34;
                border-radius: 6px;
                color: #d5e6dc;
                padding: 6px 10px;
                font-size: 12px;
            }}
            QCheckBox {{
                color: #d5e6dc;
                font-size: 12px;
                spacing: 8px;
                background-color: transparent;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid #3a5246;
                background-color: #18211d;
            }}
            QCheckBox::indicator:checked {{
                background-color: {VERDE};
                border-color: {VERDE};
            }}
            QPushButton#btn_alterar, QPushButton#btn_pausar, QPushButton#btn_cancelar, QPushButton#btn_limpar {{
                background-color: #1c2822;
                color: #ffffff;
                border: 1px solid #2c3d34;
                border-radius: 6px;
                padding: 5px 12px;
                font-weight: bold;
                font-size: 11px;
            }}
        """)

    def _montar_interface(self):
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(0, 0, 0, 0)
        layout_principal.setSpacing(0)

        faixa = QFrame()
        faixa.setFixedHeight(6)
        faixa.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9DFF74, stop:1 #149A4A); border: none;"
        )
        layout_principal.addWidget(faixa)

        miolo = QVBoxLayout()
        miolo.setContentsMargins(15, 15, 15, 15)
        miolo.setSpacing(10)
        layout_principal.addLayout(miolo)

        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(10)
        icone = QLabel()
        icone.setPixmap(logo_pixmap(42))
        icone.setStyleSheet("background: transparent; border: none;")
        marca = QLabel("greenn")
        marca.setStyleSheet("font-size: 28px; font-weight: 700; color: #ffffff; background: transparent; letter-spacing: -0.5px;")
        clube = QLabel("Club")
        clube.setStyleSheet(f"font-size: 28px; font-weight: 500; color: {VERDE}; background: transparent;")
        cabecalho.addWidget(icone)
        cabecalho.addWidget(marca)
        cabecalho.addWidget(clube)
        cabecalho.addStretch()
        miolo.addLayout(cabecalho)

        lbl_sub = QLabel("Área de membros do Greenn Club. Esta tela é o visual. A extração entra na próxima etapa.")
        lbl_sub.setStyleSheet("font-size: 14px; color: #8ea399;")
        lbl_sub.setWordWrap(True)
        miolo.addWidget(lbl_sub)

        layout_top = QHBoxLayout()
        layout_top.setSpacing(12)
        ly_esq = QVBoxLayout()
        ly_esq.setSpacing(10)

        gb_captura = QGroupBox("🔗 Link do curso")
        ly_captura = QVBoxLayout(gb_captura)
        ly_captura.setContentsMargins(10, 10, 10, 10)
        ly_captura.setSpacing(8)
        self.txt_url = QPlainTextEdit()
        self.txt_url.setPlaceholderText("Cole o link da área de membros\nhttps://greenn.club/...")
        self.txt_url.setFixedHeight(72)
        self.btn_baixar = QPushButton("📥 Listar aulas")
        self.btn_baixar.setStyleSheet(
            f"background-color: {VERDE}; color: #062016; font-weight: bold; padding: 8px; border-radius: 8px; border: none;"
        )
        self.btn_baixar.clicked.connect(self._avisar_frontend)
        ly_captura.addWidget(self.txt_url)
        ly_captura.addWidget(self.btn_baixar)
        ly_esq.addWidget(gb_captura)

        gb_destino = QGroupBox("📁 Pasta de Destino")
        ly_dest = QHBoxLayout(gb_destino)
        ly_dest.setContentsMargins(10, 10, 10, 10)
        self.txt_destino = QLineEdit(os.path.join(os.path.expanduser("~"), "Downloads", "PRT_Nexus"))
        self.btn_alterar_dest = QPushButton("Alterar")
        self.btn_alterar_dest.setObjectName("btn_alterar")
        self.btn_alterar_dest.clicked.connect(self._selecionar_pasta)
        ly_dest.addWidget(self.txt_destino)
        ly_dest.addWidget(self.btn_alterar_dest)
        ly_esq.addWidget(gb_destino)
        layout_top.addLayout(ly_esq, stretch=1)

        ly_dir = QVBoxLayout()
        ly_dir.setSpacing(10)
        gb_org = QGroupBox("📁 Organização")
        form_org = QFormLayout(gb_org)
        form_org.setContentsMargins(10, 10, 10, 10)
        form_org.setSpacing(12)

        lbl_pasta = QLabel("Pasta do curso")
        lbl_pasta.setProperty("class", "lbl-box")
        self.txt_pasta = QLineEdit()
        self.txt_pasta.setPlaceholderText("Vazio usa o nome do curso")

        lbl_qual = QLabel("Qualidade")
        lbl_qual.setProperty("class", "lbl-box")
        self.cmb_qualidade = QComboBox()
        self.cmb_qualidade.addItems([
            "Vídeo - Max Qualidade (MP4)",
            "Vídeo - 1080p (MP4)",
            "Vídeo - 720p (MP4)",
            "Apenas Áudio (MP3)",
        ])
        form_org.addRow(lbl_pasta, self.txt_pasta)
        form_org.addRow(lbl_qual, self.cmb_qualidade)
        ly_dir.addWidget(gb_org)

        gb_opcoes = QGroupBox("⚙️ Opções")
        ly_opcoes = QVBoxLayout(gb_opcoes)
        ly_opcoes.setContentsMargins(12, 12, 12, 12)
        self.chk_notif = QCheckBox("Notificar com som ao concluir")
        ly_opcoes.addWidget(self.chk_notif)
        ly_dir.addWidget(gb_opcoes)
        layout_top.addLayout(ly_dir, stretch=1)
        miolo.addLayout(layout_top)

        ly_prog = QHBoxLayout()
        self.lbl_status_global = QLabel("Aguardando o link do Greenn Club...")
        self.lbl_status_global.setStyleSheet(
            "background-color: #101614; border: 1px solid #2c3d34; border-radius: 8px; color: #8ea399; font-size: 11px; padding: 5px 10px;"
        )
        self.lbl_velocidade = QLabel("-- MiB/s | ETA: --:--")
        self.lbl_velocidade.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_velocidade.setStyleSheet(
            "background-color: #101614; border: 1px solid #2c3d34; border-radius: 8px; color: #8ea399; font-size: 11px; padding: 5px 10px;"
        )
        self.pbar_global = QProgressBar()
        self.pbar_global.setRange(0, 100)
        self.pbar_global.setValue(0)
        self.pbar_global.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pbar_global.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid #2c3d34; border-radius: 8px; text-align: center;
                background-color: #101614; color: #ffffff; font-size: 11px;
            }}
            QProgressBar::chunk {{ background-color: {VERDE}; border-radius: 6px; }}
        """)
        self.btn_pausar = QPushButton("⏸️ Pausar")
        self.btn_pausar.setObjectName("btn_pausar")
        self.btn_pausar.setEnabled(False)
        self.btn_cancelar = QPushButton("⏹️ Cancelar")
        self.btn_cancelar.setObjectName("btn_cancelar")
        self.btn_cancelar.setEnabled(False)
        ly_prog.addWidget(self.lbl_status_global, stretch=2)
        ly_prog.addWidget(self.lbl_velocidade, stretch=1)
        ly_prog.addWidget(self.pbar_global, stretch=1)
        ly_prog.addWidget(self.btn_pausar)
        ly_prog.addWidget(self.btn_cancelar)
        miolo.addLayout(ly_prog)

        gb_tabela = QFrame()
        gb_tabela.setObjectName("gb_tabela")
        ly_tab = QVBoxLayout(gb_tabela)
        ly_tab.setContentsMargins(10, 8, 10, 8)
        lbl_tab = QLabel("📦 Aulas do Greenn Club")
        lbl_tab.setStyleSheet("font-size: 13px; font-weight: bold; color: #ffffff; background: transparent; border: none;")
        self.tabela = QTableWidget(0, 4)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setHorizontalHeaderLabels(["#", "Aula", "Caminho Salvo", "Status"])
        header = self.tabela.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.tabela.setColumnWidth(0, 45)
        self.tabela.setColumnWidth(1, 280)
        self.tabela.setColumnWidth(3, 140)
        self.tabela.setStyleSheet(f"""
            QTableWidget {{
                gridline-color: #2c3d34;
                background-color: #0d1210;
                border: 1px solid #2c3d34;
                border-radius: 10px;
                color: #ffffff;
            }}
            QHeaderView::section {{
                background-color: #1c2822;
                color: #ffffff;
                border-right: 1px solid #2c3d34;
                border-bottom: 1px solid #2c3d34;
                padding: 6px;
                font-weight: bold;
            }}
        """)
        ly_tab.addWidget(lbl_tab)
        ly_tab.addWidget(self.tabela)
        miolo.addWidget(gb_tabela)

    def _selecionar_pasta(self):
        pasta = QFileDialog.getExistingDirectory(self, "Selecionar Pasta de Destino", self.txt_destino.text())
        if pasta:
            self.txt_destino.setText(pasta)

    def _avisar_frontend(self):
        QMessageBox.information(
            self,
            "Greenn Club",
            "A tela está pronta. A extração das aulas entra na próxima etapa.",
        )
