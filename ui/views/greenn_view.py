import os
import re

from PySide6.QtCore import QByteArray, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPainter, QPixmap
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
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.extractors.greenn_connector import GreennWorker

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
        self.worker = None
        self._montar_interface()
        self._aplicar_estilos()
        self._conectar_acoes()

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

        lbl_sub = QLabel("Entre na área de membros, cole o link do curso e baixe os módulos e as aulas.")
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
        self.txt_url = QLineEdit()
        self.txt_url.setPlaceholderText("https://seucurso.greenn.club/curso/...")
        ly_captura.addWidget(self.txt_url)

        ly_aula = QHBoxLayout()
        lbl_aula = QLabel("Aula:")
        lbl_aula.setProperty("class", "lbl-box")
        self.txt_aula = QLineEdit()
        self.txt_aula.setPlaceholderText("Nome no menu, para baixar só uma aula")
        ly_aula.addWidget(lbl_aula)
        ly_aula.addWidget(self.txt_aula, stretch=1)
        ly_captura.addLayout(ly_aula)

        ly_btns = QHBoxLayout()
        self.btn_avulso = QPushButton("⚡ Baixar Mídia Avulsa")
        self.btn_avulso.setStyleSheet(
            "background-color: #0066cc; color: white; font-weight: bold; padding: 8px; border-radius: 8px; border: none;"
        )
        self.btn_curso = QPushButton("🗺️ Mapear e Baixar Curso")
        self.btn_curso.setStyleSheet(
            f"background-color: {VERDE}; color: #062016; font-weight: bold; padding: 8px; border-radius: 8px; border: none;"
        )
        ly_btns.addWidget(self.btn_avulso)
        ly_btns.addWidget(self.btn_curso)
        ly_captura.addLayout(ly_btns)
        ly_esq.addWidget(gb_captura)

        gb_auth = QGroupBox("🔐 Autenticação")
        form_auth = QFormLayout(gb_auth)
        form_auth.setContentsMargins(10, 10, 10, 10)
        form_auth.setSpacing(8)
        self.txt_email = QLineEdit()
        self.txt_email.setPlaceholderText("digite seu e-mail da Greenn")
        self.txt_senha = QLineEdit()
        self.txt_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_senha.setPlaceholderText("digite sua senha")
        lbl_email = QLabel("E-mail")
        lbl_email.setProperty("class", "lbl-box")
        lbl_senha = QLabel("Senha")
        lbl_senha.setProperty("class", "lbl-box")
        form_auth.addRow(lbl_email, self.txt_email)
        form_auth.addRow(lbl_senha, self.txt_senha)
        ly_esq.addWidget(gb_auth)

        gb_destino = QGroupBox("📁 Pasta de Destino")
        ly_dest = QHBoxLayout(gb_destino)
        ly_dest.setContentsMargins(10, 10, 10, 10)
        self.txt_destino = QLineEdit(os.path.join(os.path.expanduser("~"), "Downloads", "PRT_Nexus"))
        self.btn_alterar_dest = QPushButton("Alterar")
        self.btn_alterar_dest.setObjectName("btn_alterar")
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
        self.txt_pasta.setPlaceholderText("Vazio usa o nome do curso na Greenn")

        lbl_est = QLabel("Estrutura")
        lbl_est.setProperty("class", "lbl-box")
        self.cmb_estrutura = QComboBox()
        self.cmb_estrutura.addItems([
            "Organizado Automaticamente por Módulo",
            "Todos os Vídeos na Mesma Pasta",
        ])

        lbl_mid = QLabel("Mídias")
        lbl_mid.setProperty("class", "lbl-box")
        self.cmb_midias = QComboBox()
        self.cmb_midias.addItems([
            "Extração Sequencial de Vídeos (01 -, 02 -)",
            "Manter Nome Original do Vídeo",
        ])

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
        form_org.addRow(lbl_est, self.cmb_estrutura)
        form_org.addRow(lbl_mid, self.cmb_midias)
        form_org.addRow(lbl_qual, self.cmb_qualidade)
        ly_dir.addWidget(gb_org)

        gb_opcoes = QGroupBox("⚙️ Opções")
        ly_opcoes = QVBoxLayout(gb_opcoes)
        ly_opcoes.setContentsMargins(12, 12, 12, 12)
        self.chk_anexos = QCheckBox("Baixar materiais anexos das aulas (PDFs, ZIPs)")
        self.chk_anexos.setChecked(True)
        self.chk_txt = QCheckBox("Gerar arquivo .txt com índice e descrição das aulas")
        self.chk_notif = QCheckBox("Notificar com som ao concluir")
        ly_opcoes.addWidget(self.chk_anexos)
        ly_opcoes.addWidget(self.chk_txt)
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
        cab_tab = QHBoxLayout()
        lbl_tab = QLabel("📦 Aulas do Greenn Club")
        lbl_tab.setStyleSheet("font-size: 13px; font-weight: bold; color: #ffffff; background: transparent; border: none;")
        self.btn_limpar = QPushButton("Limpar concluídos")
        self.btn_limpar.setObjectName("btn_limpar")
        cab_tab.addWidget(lbl_tab)
        cab_tab.addStretch()
        cab_tab.addWidget(self.btn_limpar)
        self.tabela = QTableWidget(0, 4)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setHorizontalHeaderLabels(["#", "Aula", "Caminho Salvo", "Status"])
        self.tabela.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        header = self.tabela.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        self.tabela.setColumnWidth(0, 45)
        self.tabela.setColumnWidth(1, 300)
        self.tabela.setColumnWidth(2, 400)
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
                border-top: none;
                border-left: none;
                padding: 6px;
                font-weight: bold;
            }}
        """)
        ly_tab.addLayout(cab_tab)
        ly_tab.addWidget(self.tabela)
        miolo.addWidget(gb_tabela)

    def _conectar_acoes(self):
        self.btn_avulso.clicked.connect(lambda: self._iniciar_download(modo_avulso=True))
        self.btn_curso.clicked.connect(lambda: self._iniciar_download(modo_avulso=False))
        self.btn_alterar_dest.clicked.connect(self._selecionar_pasta)
        self.btn_pausar.clicked.connect(self._toggle_pausar_resumir)
        self.btn_cancelar.clicked.connect(self._cancelar_download)
        self.btn_limpar.clicked.connect(self._limpar_concluidos)
        self.tabela.itemDoubleClicked.connect(self._abrir_item_tabela)

    def _selecionar_pasta(self):
        pasta = QFileDialog.getExistingDirectory(self, "Selecionar Pasta de Destino", self.txt_destino.text())
        if pasta:
            self.txt_destino.setText(pasta)

    def _abrir_item_tabela(self, item):
        caminho_item = self.tabela.item(item.row(), 2)
        if not caminho_item or not caminho_item.text():
            return
        caminho = caminho_item.text()
        if os.path.exists(caminho):
            if os.path.isfile(caminho):
                caminho = os.path.dirname(caminho)
            QDesktopServices.openUrl(QUrl.fromLocalFile(caminho))

    def _toggle_pausar_resumir(self):
        if not self.worker or not self.worker.isRunning():
            return
        if self.btn_pausar.text() == "⏸️ Pausar":
            self.btn_pausar.setText("▶️ Retomar")
            self.worker.pausar()
        else:
            self.btn_pausar.setText("⏸️ Pausar")
            self.worker.resumir()

    def _cancelar_download(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancelar()
            self.worker.terminate()
            self.worker.wait()
            self.lbl_status_global.setText("Download cancelado pelo usuário.")
            self.lbl_velocidade.setText("-- MiB/s | ETA: --:--")
            self.pbar_global.setValue(0)
            self._remover_linhas_incompletas()
            self.btn_avulso.setEnabled(True)
            self.btn_curso.setEnabled(True)
            self.btn_pausar.setEnabled(False)
            self.btn_cancelar.setEnabled(False)
            self.btn_pausar.setText("⏸️ Pausar")

    def _limpar_concluidos(self):
        em_andamento = bool(self.worker and self.worker.isRunning())
        for row in reversed(range(self.tabela.rowCount())):
            pbar = self.tabela.cellWidget(row, 3)
            if isinstance(pbar, QProgressBar) and (pbar.value() >= 100 or not em_andamento):
                self.tabela.removeRow(row)

    def _remover_linhas_incompletas(self):
        for row in reversed(range(self.tabela.rowCount())):
            pbar = self.tabela.cellWidget(row, 3)
            if isinstance(pbar, QProgressBar) and pbar.value() < 100:
                self.tabela.removeRow(row)

    def _iniciar_download(self, modo_avulso):
        url = self.txt_url.text().strip()
        email = self.txt_email.text().strip()
        senha = self.txt_senha.text().strip()
        destino = self.txt_destino.text().strip()
        if not url or not email or not senha:
            QMessageBox.warning(self, "Campos Vazios", "Preencha o Link, E-mail e Senha antes de iniciar!")
            return
        nome_aula = self.txt_aula.text().strip()
        if modo_avulso and not nome_aula:
            QMessageBox.warning(self, "Nome da aula", "Digite o nome da aula como aparece no menu do curso.")
            return
        opcoes = {
            "baixar_anexos": self.chk_anexos.isChecked(),
            "gerar_txt": self.chk_txt.isChecked(),
            "notificar_som": self.chk_notif.isChecked(),
            "qualidade": self.cmb_qualidade.currentText(),
            "nome_conteudo": self.txt_pasta.text().strip(),
            "estrutura": self.cmb_estrutura.currentText(),
            "midias": self.cmb_midias.currentText(),
            "nome_aula": nome_aula,
        }
        self.btn_avulso.setEnabled(False)
        self.btn_curso.setEnabled(False)
        self.btn_pausar.setEnabled(True)
        self.btn_cancelar.setEnabled(True)
        self.btn_pausar.setText("⏸️ Pausar")
        self.worker = GreennWorker(url, email, senha, destino, modo_avulso=modo_avulso, opcoes=opcoes)
        self.worker.progresso.connect(self._on_progresso)
        self.worker.velocidade.connect(self.lbl_velocidade.setText)
        self.worker.item_progresso.connect(self._on_item_progresso)
        self.worker.item_concluido.connect(self._on_item_concluido)
        self.worker.concluido.connect(self._on_concluido)
        self.worker.start()

    def _on_concluido(self, sucesso, mensagem):
        self.btn_avulso.setEnabled(True)
        self.btn_curso.setEnabled(True)
        self.btn_pausar.setEnabled(False)
        self.btn_cancelar.setEnabled(False)
        if self.chk_notif.isChecked():
            from PySide6.QtWidgets import QApplication
            QApplication.beep()
        if sucesso:
            QMessageBox.information(self, "Greenn Club", mensagem)
        else:
            QMessageBox.critical(self, "Greenn Club", mensagem)

    def _on_progresso(self, msg, pct):
        self.pbar_global.setValue(pct)
        self.lbl_status_global.setText(msg)

    def _criar_barra_status(self):
        pbar = QProgressBar()
        pbar.setRange(0, 100)
        pbar.setValue(0)
        pbar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pbar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid #2c3d34; border-radius: 6px; text-align: center;
                background-color: #101614; color: #ffffff; font-size: 11px; font-weight: bold;
            }}
            QProgressBar::chunk {{ background-color: {VERDE}; border-radius: 4px; }}
        """)
        return pbar

    def _on_item_progresso(self, num_str, pct):
        for row in range(self.tabela.rowCount()):
            item_num = self.tabela.item(row, 0)
            if item_num and item_num.text() == str(num_str):
                pbar = self.tabela.cellWidget(row, 3)
                if isinstance(pbar, QProgressBar):
                    pbar.setValue(int(pct))
                break

    def _on_item_concluido(self, item):
        num = str(item.get("num", ""))
        titulo = re.sub(r"^\d{2}\s+-\s+", "", str(item.get("titulo", ""))).replace("_", " ").strip()
        caminho = str(item.get("caminho", ""))
        status = str(item.get("status", ""))
        linha = -1
        for row in range(self.tabela.rowCount()):
            item_num = self.tabela.item(row, 0)
            if item_num and item_num.text() == num:
                linha = row
                break
        if linha < 0:
            linha = self.tabela.rowCount()
            self.tabela.insertRow(linha)
            item_num = QTableWidgetItem(num)
            item_num.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tabela.setItem(linha, 0, item_num)
            self.tabela.setItem(linha, 1, QTableWidgetItem(titulo))
            self.tabela.setItem(linha, 2, QTableWidgetItem(caminho))
            self.tabela.setCellWidget(linha, 3, self._criar_barra_status())
        else:
            self.tabela.setItem(linha, 2, QTableWidgetItem(caminho))
        pbar = self.tabela.cellWidget(linha, 3)
        if not isinstance(pbar, QProgressBar):
            return
        if status == "Concluído":
            pbar.setValue(100)
            pbar.setFormat("Concluído (100%)")
        elif status == "Sem vídeo":
            pbar.setValue(100)
            pbar.setFormat("Sem vídeo")
        elif status in ("Erro", "Protegido"):
            pbar.setValue(100)
            pbar.setFormat(status)
            pbar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #2c3d34; border-radius: 6px; text-align: center;
                    background-color: #101614; color: #ffffff; font-size: 11px; font-weight: bold;
                }
                QProgressBar::chunk { background-color: #e74c3c; border-radius: 4px; }
            """)
        else:
            pbar.setFormat("%p%")
