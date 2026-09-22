import os
import re
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QGroupBox, QLineEdit,
    QComboBox, QPushButton, QMessageBox, QTableWidget, QTableWidgetItem, QProgressBar,
    QHeaderView, QFileDialog, QCheckBox, QFrame
)
from services.extractors.universo_mapper import UniversoWorker


class UniversoView(QWidget):
    def __init__(self, parent=None, downloads_view=None):
        super().__init__(parent)
        self.downloads_view = downloads_view
        self.worker = None

        self._montar_interface()
        self._aplicar_estilos()
        self._conectar_acoes()

    def _aplicar_estilos(self):
        """Aplica o mesmo estilo visual do Conector Chip 7."""
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
            }

            QGroupBox {
                background-color: #1e1e1e;
                border: 1px solid #333333;
                border-radius: 8px;
                margin-top: 4px;
                padding-top: 22px;
                padding-bottom: 8px;
                font-size: 13px;
                font-weight: bold;
                color: #ffffff;
            }

            QGroupBox::title {
                subcontrol-origin: padding;
                subcontrol-position: top left;
                left: 10px;
                top: 6px;
                padding: 0 4px;
                background-color: transparent;
                color: #ffffff;
            }
            QFrame#gb_tabela {
                background-color: #1e1e1e;
                border: 1px solid #3c3c3c;
                border-radius: 12px;
            }

            QLineEdit, QComboBox {
                background-color: #252526;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                color: #ffffff;
                padding: 6px 10px;
                font-size: 12px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #0066cc;
            }

            QLabel.lbl-box {
                background-color: #252526;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                color: #cccccc;
                padding: 6px 10px;
                font-size: 12px;
            }

            QCheckBox {
                color: #cccccc;
                font-size: 12px;
                spacing: 8px;
                background-color: transparent;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid #444444;
                background-color: #252526;
            }
            QCheckBox::indicator:checked {
                background-color: #0066cc;
                border-color: #0066cc;
            }

            QPushButton#btn_alterar {
                background-color: #333333;
                color: #ffffff;
                border: 1px solid #444444;
                border-radius: 6px;
                padding: 5px 14px;
                font-weight: bold;
            }
            QPushButton#btn_alterar:hover {
                background-color: #444444;
            }

            QPushButton#btn_pausar, QPushButton#btn_cancelar {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 5px 12px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton#btn_pausar:hover {
                background-color: #3a3a3a;
            }
            QPushButton#btn_cancelar:hover {
                background-color: #8b0000;
            }

            QPushButton#btn_limpar {
                background-color: #2b2b2b;
                color: #aaaaaa;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton#btn_limpar:hover {
                background-color: #c0392b;
                color: #ffffff;
            }
        """)

    def _montar_interface(self):
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(15, 15, 15, 15)
        layout_principal.setSpacing(10)

        lbl_titulo = QLabel("Conector Universo Técnico")
        lbl_titulo.setStyleSheet("font-size: 24px; font-weight: bold; color: #ffffff;")
        lbl_sub = QLabel("Capture, extraia e gerencie conteúdos diretamente do Universo Técnico.")
        lbl_sub.setStyleSheet("font-size: 14px; color: #888888;")
        layout_principal.addWidget(lbl_titulo)
        layout_principal.addWidget(lbl_sub)

        layout_top = QHBoxLayout()
        layout_top.setSpacing(12)

        ly_esq = QVBoxLayout()
        ly_esq.setSpacing(10)

        gb_captura = QGroupBox("🔗 Captura de Mídia - Universo Técnico")
        ly_captura = QVBoxLayout(gb_captura)
        ly_captura.setContentsMargins(10, 10, 10, 10)
        ly_captura.setSpacing(8)

        self.txt_url = QLineEdit()
        self.txt_url.setPlaceholderText("Cole o link do vídeo, aula ou curso aqui...")
        ly_captura.addWidget(self.txt_url)

        ly_qual = QHBoxLayout()
        lbl_qual = QLabel("Qualidade:")
        lbl_qual.setProperty("class", "lbl-box")
        self.cmb_qualidade = QComboBox()
        self.cmb_qualidade.addItems([
            "Vídeo - Max Qualidade (MP4)",
            "Vídeo - 1080p (MP4)",
            "Vídeo - 720p (MP4)",
            "Apenas Áudio (MP3)"
        ])
        ly_qual.addWidget(lbl_qual)
        ly_qual.addWidget(self.cmb_qualidade, stretch=1)
        ly_captura.addLayout(ly_qual)

        ly_btns = QHBoxLayout()
        self.btn_avulso = QPushButton("⚡ Baixar Mídia Avulsa")
        self.btn_avulso.setStyleSheet("background-color: #0066cc; color: white; font-weight: bold; padding: 8px; border-radius: 8px; border: none;")

        self.btn_curso = QPushButton("🗺️ Mapear e Baixar Curso / Playlist")
        self.btn_curso.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; padding: 8px; border-radius: 8px; border: none;")

        ly_btns.addWidget(self.btn_avulso)
        ly_btns.addWidget(self.btn_curso)
        ly_captura.addLayout(ly_btns)

        ly_esq.addWidget(gb_captura)

        gb_auth = QGroupBox("🔐 Autenticação (Áreas Pagas / Privadas)")
        form_auth = QFormLayout(gb_auth)
        form_auth.setContentsMargins(10, 10, 10, 10)
        form_auth.setSpacing(8)

        self.txt_email = QLineEdit()
        self.txt_email.setPlaceholderText("digite seu e-mail do Universo Técnico")
        self.txt_senha = QLineEdit()
        self.txt_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_senha.setPlaceholderText("digite sua senha")

        lbl_email = QLabel("E-mail / Usuário")
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

        gb_org = QGroupBox("📁 Organização de Pastas (Curso / Playlist)")
        form_org = QFormLayout(gb_org)
        form_org.setContentsMargins(10, 10, 10, 10)
        form_org.setSpacing(12)

        lbl_nome_cnt = QLabel("Nome do Conteúdo")
        lbl_nome_cnt.setProperty("class", "lbl-box")
        self.txt_nome_conteudo = QLineEdit("Universo Técnico - Curso Extraído")

        lbl_est = QLabel("Estrutura")
        lbl_est.setProperty("class", "lbl-box")
        self.cmb_estrutura = QComboBox()
        self.cmb_estrutura.addItems([
            "Organizado Automaticamente por Módulo",
            "Todos os Vídeos na Mesma Pasta"
        ])

        lbl_mid = QLabel("Mídias")
        lbl_mid.setProperty("class", "lbl-box")
        self.cmb_midias = QComboBox()
        self.cmb_midias.addItems([
            "Extração Sequencial de Vídeos (01 -, 02 -)",
            "Manter Nome Original do Vídeo"
        ])

        form_org.addRow(lbl_nome_cnt, self.txt_nome_conteudo)
        form_org.addRow(lbl_est, self.cmb_estrutura)
        form_org.addRow(lbl_mid, self.cmb_midias)

        ly_dir.addWidget(gb_org)

        gb_opcoes = QGroupBox("⚙️ Opções Extras de Extração")
        ly_opcoes = QVBoxLayout(gb_opcoes)
        ly_opcoes.setContentsMargins(12, 12, 12, 12)
        ly_opcoes.setSpacing(10)

        self.chk_anexos = QCheckBox("Baixar materiais anexos das aulas (PDFs, ZIPs, Apostilas)")
        self.chk_anexos.setChecked(True)
        self.chk_txt = QCheckBox("Gerar arquivo .txt com índice e descrição das aulas")
        self.chk_notif = QCheckBox("Notificar com som ao concluir todos os downloads")

        ly_opcoes.addWidget(self.chk_anexos)
        ly_opcoes.addWidget(self.chk_txt)
        ly_opcoes.addWidget(self.chk_notif)

        ly_dir.addWidget(gb_opcoes)

        layout_top.addLayout(ly_dir, stretch=1)
        layout_principal.addLayout(layout_top)

        ly_prog_geral = QHBoxLayout()

        self.lbl_status_global = QLabel("Aguardando link de download...")
        self.lbl_status_global.setStyleSheet("""
            background-color: #1e1e1e;
            border: 1px solid #3a3a3a;
            border-radius: 8px;
            color: #aaaaaa;
            font-size: 11px;
            padding: 5px 10px;
        """)

        self.lbl_velocidade = QLabel("-- MiB/s | ETA: --:--")
        self.lbl_velocidade.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_velocidade.setStyleSheet("""
            background-color: #1e1e1e;
            border: 1px solid #3a3a3a;
            border-radius: 8px;
            color: #aaaaaa;
            font-size: 11px;
            padding: 5px 10px;
        """)

        self.pbar_global = QProgressBar()
        self.pbar_global.setRange(0, 100)
        self.pbar_global.setValue(0)
        self.pbar_global.setTextVisible(True)
        self.pbar_global.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pbar_global.setStyleSheet("""
            QProgressBar {
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                text-align: center;
                background-color: #1e1e1e;
                color: #ffffff;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background-color: #2ecc71;
                border-radius: 6px;
            }
        """)

        self.btn_pausar = QPushButton("⏸️ Pausar")
        self.btn_pausar.setObjectName("btn_pausar")
        self.btn_pausar.setEnabled(False)

        self.btn_cancelar = QPushButton("⏹️ Cancelar")
        self.btn_cancelar.setObjectName("btn_cancelar")
        self.btn_cancelar.setEnabled(False)

        ly_prog_geral.addWidget(self.lbl_status_global, stretch=2)
        ly_prog_geral.addWidget(self.lbl_velocidade, stretch=1)
        ly_prog_geral.addWidget(self.pbar_global, stretch=1)
        ly_prog_geral.addWidget(self.btn_pausar)
        ly_prog_geral.addWidget(self.btn_cancelar)

        layout_principal.addLayout(ly_prog_geral)

        gb_tabela = QFrame()
        gb_tabela.setObjectName("gb_tabela")
        ly_tab = QVBoxLayout(gb_tabela)
        ly_tab.setContentsMargins(10, 8, 10, 8)
        ly_tab.setSpacing(6)

        ly_tab_top = QHBoxLayout()
        ly_tab_top.setContentsMargins(0, 0, 0, 0)
        ly_tab_top.setSpacing(8)

        lbl_tab_title = QLabel("📦 Mídias Concluídas do Universo Técnico (Duplo clique para abrir a pasta)")
        lbl_tab_title.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #ffffff; background: transparent; border: none; padding: 0;"
        )
        lbl_tab_title.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        ly_tab_top.addWidget(lbl_tab_title, 1, Qt.AlignmentFlag.AlignVCenter)

        self.btn_limpar = QPushButton("🗑️ Limpar Concluídos")
        self.btn_limpar.setObjectName("btn_limpar")
        ly_tab_top.addWidget(self.btn_limpar, 0, Qt.AlignmentFlag.AlignVCenter)

        ly_tab.addLayout(ly_tab_top)

        self.tabela = QTableWidget(0, 4)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setHorizontalHeaderLabels(["#", "Título / Nome do Arquivo", "Caminho Salvo", "Status"])
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

        self._configurar_estilo_tabela(self.tabela)
        ly_tab.addWidget(self.tabela)

        layout_principal.addWidget(gb_tabela)

    def _configurar_estilo_tabela(self, tabela):
        tabela.setShowGrid(True)
        tabela.setStyleSheet("""
            QTableWidget {
                gridline-color: #3a3a3a;
                background-color: #1a1a1a;
                border: 1px solid #3a3a3a;
                border-radius: 10px;
            }
            QTableWidget::item {
                border: none;
                padding: 4px;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #2b2b2b;
                color: #ffffff;
                border-right: 1px solid #3a3a3a;
                border-bottom: 1px solid #3a3a3a;
                border-top: none;
                border-left: none;
                padding: 6px;
                font-weight: bold;
            }
        """)
        tabela.setColumnWidth(0, 45)

    def _conectar_acoes(self):
        self.btn_avulso.clicked.connect(lambda: self._iniciar_download(modo_avulso=True))
        self.btn_curso.clicked.connect(lambda: self._iniciar_download(modo_avulso=False))
        self.btn_alterar_dest.clicked.connect(self._selecionar_pasta_destino)
        self.btn_pausar.clicked.connect(self._toggle_pausar_resumir)
        self.btn_cancelar.clicked.connect(self._cancelar_download)
        self.btn_limpar.clicked.connect(self._limpar_concluidos)
        self.tabela.itemDoubleClicked.connect(self._abrir_item_tabela)

    def _selecionar_pasta_destino(self):
        pasta = QFileDialog.getExistingDirectory(self, "Selecionar Pasta de Destino", self.txt_destino.text())
        if pasta:
            self.txt_destino.setText(pasta)

    def _abrir_item_tabela(self, item):
        row = item.row()
        caminho_item = self.tabela.item(row, 2)
        if caminho_item and caminho_item.text():
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
            if hasattr(self.worker, "pausar"):
                self.worker.pausar()
        else:
            self.btn_pausar.setText("⏸️ Pausar")
            if hasattr(self.worker, "resumir"):
                self.worker.resumir()

    def _cancelar_download(self):
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
            self.lbl_status_global.setText("Download cancelado pelo usuário.")
            self.lbl_velocidade.setText("-- MiB/s | ETA: --:--")
            self.pbar_global.setValue(0)

            self.btn_avulso.setEnabled(True)
            self.btn_curso.setEnabled(True)
            self.btn_pausar.setEnabled(False)
            self.btn_cancelar.setEnabled(False)
            self.btn_pausar.setText("⏸️ Pausar")

    def _limpar_concluidos(self):
        for row in reversed(range(self.tabela.rowCount())):
            pbar = self.tabela.cellWidget(row, 3)
            if isinstance(pbar, QProgressBar) and pbar.value() >= 100:
                self.tabela.removeRow(row)

    def _iniciar_download(self, modo_avulso):
        url = self.txt_url.text().strip()
        email = self.txt_email.text().strip()
        senha = self.txt_senha.text().strip()
        destino = self.txt_destino.text().strip()

        if not url or not email or not senha:
            QMessageBox.warning(self, "Campos Vazios", "Preencha o Link, E-mail e Senha antes de iniciar!")
            return

        self.tabela.setRowCount(0)
        self._configurar_estilo_tabela(self.tabela)

        self.btn_avulso.setEnabled(False)
        self.btn_curso.setEnabled(False)
        self.btn_pausar.setEnabled(True)
        self.btn_cancelar.setEnabled(True)
        self.btn_pausar.setText("⏸️ Pausar")

        self.lbl_velocidade.setText("-- MiB/s | ETA: --:--")
        self.worker = UniversoWorker(url, email, senha, destino, modo_avulso=modo_avulso)
        self.worker.progresso.connect(self._on_progresso)
        self.worker.velocidade.connect(self._on_velocidade)
        self.worker.item_progresso.connect(self._on_item_progresso)
        self.worker.item_concluido.connect(self._on_item_concluido)
        self.worker.concluido.connect(self._on_concluido)
        self.worker.start()

    def _on_progresso(self, msg, pct):
        self.pbar_global.setValue(pct)
        self.lbl_status_global.setText(msg)

    def _on_velocidade(self, texto):
        self.lbl_velocidade.setText(texto)

    def _criar_barra_status(self):
        pbar = QProgressBar()
        pbar.setRange(0, 100)
        pbar.setValue(0)
        pbar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pbar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                text-align: center;
                background-color: #1e1e1e;
                color: #ffffff;
                font-size: 11px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #2ecc71;
                border-radius: 4px;
            }
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
        titulo_bruto = str(item.get("titulo", ""))
        caminho = str(item.get("caminho", ""))
        status = str(item.get("status", ""))

        titulo_exibicao = re.sub(r"^\d+[\s\-_]*", "", titulo_bruto)
        titulo_exibicao = re.sub(r"^[\s\-_]+", "", titulo_exibicao).replace("_", " ").strip()

        linha_existente = -1
        for row in range(self.tabela.rowCount()):
            item_num = self.tabela.item(row, 0)
            if item_num and item_num.text() == num:
                linha_existente = row
                break

        if linha_existente >= 0:
            pbar = self.tabela.cellWidget(linha_existente, 3)
            if isinstance(pbar, QProgressBar):
                if status == "Concluído":
                    pbar.setValue(100)
                    pbar.setFormat("Concluído (100%)")
                elif status == "Erro":
                    pbar.setValue(100)
                    pbar.setFormat("Erro")
                    pbar.setStyleSheet("""
                        QProgressBar {
                            border: 1px solid #3a3a3a;
                            border-radius: 6px;
                            text-align: center;
                            background-color: #1e1e1e;
                            color: #ffffff;
                            font-size: 11px;
                            font-weight: bold;
                        }
                        QProgressBar::chunk {
                            background-color: #e74c3c;
                            border-radius: 4px;
                        }
                    """)
        else:
            row = self.tabela.rowCount()
            self.tabela.insertRow(row)

            item_num = QTableWidgetItem(num)
            item_num.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tabela.setItem(row, 0, item_num)

            self.tabela.setItem(row, 1, QTableWidgetItem(titulo_exibicao))
            self.tabela.setItem(row, 2, QTableWidgetItem(caminho))

            pbar = self._criar_barra_status()
            if status == "Concluído":
                pbar.setValue(100)
                pbar.setFormat("Concluído (100%)")
            else:
                pbar.setValue(0)
                pbar.setFormat("%p%")

            self.tabela.setCellWidget(row, 3, pbar)
            self.tabela.setColumnWidth(0, 45)

    def _on_concluido(self, sucesso, mensagem):
        self.btn_avulso.setEnabled(True)
        self.btn_curso.setEnabled(True)
        self.btn_pausar.setEnabled(False)
        self.btn_cancelar.setEnabled(False)

        if self.chk_notif.isChecked():
            from PySide6.QtWidgets import QApplication
            QApplication.beep()

        if sucesso:
            QMessageBox.information(self, "Universo Técnico", mensagem)
        else:
            QMessageBox.critical(self, "Universo Técnico - Erro", mensagem)
