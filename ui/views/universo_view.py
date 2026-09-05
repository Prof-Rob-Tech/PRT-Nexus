import os
import re
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QGroupBox, QLineEdit, 
    QComboBox, QPushButton, QMessageBox, QTableWidget, QTableWidgetItem, QProgressBar, 
    QHeaderView, QFileDialog
)
from services.extractors.universo_mapper import UniversoWorker

class UniversoView(QWidget):
    def __init__(self, parent=None, downloads_view=None):
        super().__init__(parent)
        self.downloads_view = downloads_view
        self.worker = None

        self._montar_interface()
        self._conectar_acoes()

    def _montar_interface(self):
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(15, 15, 15, 15)
        layout_principal.setSpacing(10)

        # Cabeçalho
        lbl_titulo = QLabel("Conector Universo Técnico")
        lbl_titulo.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        lbl_sub = QLabel("Capture, extraia e gerencie conteúdos diretamente do Universo Técnico.")
        lbl_sub.setStyleSheet("font-size: 11px; color: #888888;")
        layout_principal.addWidget(lbl_titulo)
        layout_principal.addWidget(lbl_sub)

        # Área Superior (Duas Colunas)
        layout_top = QHBoxLayout()
        layout_top.setSpacing(12)

        # ================= COLUNA ESQUERDA =================
        ly_esq = QVBoxLayout()
        ly_esq.setSpacing(10)

        # 1. Captura de Mídia
        gb_captura = QGroupBox("Captura de Mídia - Universo Técnico")
        ly_captura = QVBoxLayout(gb_captura)
        ly_captura.setSpacing(8)

        self.txt_url = QLineEdit()
        self.txt_url.setPlaceholderText("Cole o link do vídeo, aula ou curso aqui...")
        ly_captura.addWidget(self.txt_url)

        # Seleção de Qualidade
        ly_qual = QHBoxLayout()
        lbl_qual = QLabel("Qualidade:")
        lbl_qual.setStyleSheet("color: #cccccc;")
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

        # Botões de Ação
        ly_btns = QHBoxLayout()
        self.btn_avulso = QPushButton("⚡ Baixar Mídia Avulsa")
        self.btn_avulso.setStyleSheet("background-color: #0066cc; color: white; font-weight: bold; padding: 7px; border-radius: 4px;")
        
        self.btn_curso = QPushButton("🗺️ Mapear e Baixar Curso / Playlist")
        self.btn_curso.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; padding: 7px; border-radius: 4px;")
        
        ly_btns.addWidget(self.btn_avulso)
        ly_btns.addWidget(self.btn_curso)
        ly_captura.addLayout(ly_btns)

        ly_esq.addWidget(gb_captura)

        # 2. Autenticação (Com FormLayout e Rótulos)
        gb_auth = QGroupBox("Autenticação (Áreas Pagas / Privadas)")
        form_auth = QFormLayout(gb_auth)
        form_auth.setSpacing(8)

        self.txt_email = QLineEdit()
        self.txt_email.setPlaceholderText("E-mail / Usuário")
        self.txt_senha = QLineEdit()
        self.txt_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_senha.setPlaceholderText("Senha")

        lbl_email = QLabel("E-mail / Usuário")
        lbl_email.setStyleSheet("color: #cccccc;")
        lbl_senha = QLabel("Senha")
        lbl_senha.setStyleSheet("color: #cccccc;")

        form_auth.addRow(lbl_email, self.txt_email)
        form_auth.addRow(lbl_senha, self.txt_senha)

        ly_esq.addWidget(gb_auth)

        # 3. Pasta de Destino
        gb_destino = QGroupBox("Pasta de Destino")
        ly_dest = QHBoxLayout(gb_destino)
        self.txt_destino = QLineEdit(os.path.join(os.path.expanduser("~"), "Downloads", "PRT_Nexus"))
        self.btn_alterar_dest = QPushButton("Alterar")
        self.btn_alterar_dest.setStyleSheet("padding: 4px 12px;")
        ly_dest.addWidget(self.txt_destino)
        ly_dest.addWidget(self.btn_alterar_dest)

        ly_esq.addWidget(gb_destino)

        layout_top.addLayout(ly_esq, stretch=2)

        # ================= COLUNA DIREITA =================
        gb_org = QGroupBox("Organização de Pastas (Curso / Playlist)")
        form_org = QFormLayout(gb_org)
        form_org.setSpacing(12)

        lbl_nome_cnt = QLabel("Nome do Conteúdo")
        lbl_nome_cnt.setStyleSheet("color: #cccccc;")
        self.txt_nome_conteudo = QLineEdit("Nome do Conteúdo / Curso / Playlist")
        
        lbl_est = QLabel("Estrutura")
        lbl_est.setStyleSheet("color: #cccccc;")
        self.txt_estrutura = QLineEdit("Organizado Automaticamente por Módulo")
        self.txt_estrutura.setReadOnly(True)

        lbl_mid = QLabel("Mídias")
        lbl_mid.setStyleSheet("color: #cccccc;")
        self.txt_midias = QLineEdit("Extração Sequencial de Vídeos")
        self.txt_midias.setReadOnly(True)

        form_org.addRow(lbl_nome_cnt, self.txt_nome_conteudo)
        form_org.addRow(lbl_est, self.txt_estrutura)
        form_org.addRow(lbl_mid, self.txt_midias)

        layout_top.addWidget(gb_org, stretch=1)

        layout_principal.addLayout(layout_top)

        # ================= BARRA DE PROGRESSO GERAL =================
        ly_prog_geral = QHBoxLayout()
        self.lbl_status_global = QLabel("Aguardando link de download...")
        self.lbl_status_global.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        
        self.pbar_global = QProgressBar()
        self.pbar_global.setRange(0, 100)
        self.pbar_global.setValue(0)
        self.pbar_global.setTextVisible(True)
        self.pbar_global.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pbar_global.setStyleSheet("""
            QProgressBar {
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                text-align: center;
                background-color: #1e1e1e;
                color: #ffffff;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background-color: #2ecc71;
            }
        """)

        ly_prog_geral.addWidget(self.lbl_status_global, stretch=1)
        ly_prog_geral.addWidget(self.pbar_global, stretch=2)
        layout_principal.addLayout(ly_prog_geral)

        # ================= TABELA DE MÍDIAS =================
        gb_tabela = QGroupBox("Mídias Concluídas do Universo Técnico")
        ly_tab = QVBoxLayout(gb_tabela)

        self.tabela = QTableWidget(0, 4)
        self.tabela.setHorizontalHeaderLabels(["#", "Título / Nome do Arquivo", "Caminho Salvo", "Status"])
        self.tabela.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabela.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tabela.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.tabela.setColumnWidth(3, 110)

        self._configurar_estilo_tabela(self.tabela)
        ly_tab.addWidget(self.tabela)

        layout_principal.addWidget(gb_tabela)

    def _configurar_estilo_tabela(self, tabela):
        tabela.setShowGrid(True)
        tabela.setStyleSheet("""
            QTableWidget {
                gridline-color: #3a3a3a;
                background-color: #1a1a1a;
            }
            QTableWidget::item {
                border: none;
                padding: 4px;
            }
            QHeaderView::section {
                background-color: #2b2b2b;
                color: #ffffff;
                border-right: 1px solid #3a3a3a;
                border-bottom: 1px solid #3a3a3a;
                border-top: none;
                border-left: none;
                padding: 4px;
                font-weight: bold;
            }
        """)
        tabela.setColumnWidth(0, 45)

    def _conectar_acoes(self):
        self.btn_avulso.clicked.connect(lambda: self._iniciar_download(modo_avulso=True))
        self.btn_curso.clicked.connect(lambda: self._iniciar_download(modo_avulso=False))
        self.btn_alterar_dest.clicked.connect(self._selecionar_pasta_destino)

    def _selecionar_pasta_destino(self):
        pasta = QFileDialog.getExistingDirectory(self, "Selecionar Pasta de Destino", self.txt_destino.text())
        if pasta:
            self.txt_destino.setText(pasta)

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

        self.worker = UniversoWorker(url, email, senha, destino, modo_avulso=modo_avulso)
        self.worker.progresso.connect(self._on_progresso)
        self.worker.item_progresso.connect(self._on_item_progresso)
        self.worker.item_concluido.connect(self._on_item_concluido)
        self.worker.concluido.connect(self._on_concluido)
        self.worker.start()

    def _on_progresso(self, msg, pct):
        self.pbar_global.setValue(pct)
        self.lbl_status_global.setText(msg)

    def _criar_barra_status(self):
        pbar = QProgressBar()
        pbar.setRange(0, 100)
        pbar.setValue(0)
        pbar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pbar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                text-align: center;
                background-color: #1e1e1e;
                color: #ffffff;
                font-size: 11px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #2ecc71;
                border-radius: 3px;
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

        titulo_exibicao = re.sub(r'^\d+[\s\-_]*', '', titulo_bruto)
        titulo_exibicao = re.sub(r'^[\s\-_]+', '', titulo_exibicao).replace('_', ' ').strip()

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
                            border-radius: 4px;
                            text-align: center;
                            background-color: #1e1e1e;
                            color: #ffffff;
                            font-size: 11px;
                            font-weight: bold;
                        }
                        QProgressBar::chunk {
                            background-color: #e74c3c;
                            border-radius: 3px;
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

        if sucesso:
            QMessageBox.information(self, "Universo Técnico", mensagem)
        else:
            QMessageBox.critical(self, "Universo Técnico - Erro", mensagem)