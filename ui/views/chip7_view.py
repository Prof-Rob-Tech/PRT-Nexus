import os
import re
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QGroupBox, QLineEdit, 
    QComboBox, QPushButton, QMessageBox, QTableWidget, QTableWidgetItem, QProgressBar, 
    QHeaderView, QFileDialog
)
from services.extractors.chip7_mapper import Chip7Worker


class Chip7View(QWidget):
    def __init__(self, parent=None, downloads_view=None):
        super().__init__(parent)
        self.downloads_view = downloads_view
        self.worker = None

        self._montar_interface()
        self._aplicar_estilos()
        self._conectar_acoes()

    def _aplicar_estilos(self):
        """Aplica o CSS com cantos arredondados, foco suave e sem destaques azuis."""
        self.setStyleSheet("""
            QGroupBox {
                background-color: #252526;
                border: 1px solid #3c3c3c;
                border-radius: 12px;
                margin-top: 18px;
                padding-top: 16px;
                padding-bottom: 10px;
                font-weight: bold;
                color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: border;
                subcontrol-position: top left;
                left: 14px;
                top: 6px;
                padding: 0 6px;
                background-color: #252526;
                color: #ffffff;
            }

            QLineEdit, QComboBox {
                background-color: #1e1e1e;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                color: #ffffff;
                padding: 6px 10px;
                font-size: 12px;
                /* Remove a seleção azul padrão do texto */
                selection-background-color: #3a3a3a;
                selection-color: #ffffff;
            }
            /* Foco discreto em cinza médio (sem linha azul) */
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #555555;
            }
            QLineEdit:read-only {
                background-color: #181818;
                color: #888888;
            }

            QLabel.lbl-box {
                background-color: #1e1e1e;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                color: #cccccc;
                padding: 6px 10px;
                font-size: 12px;
            }

            QPushButton#btn_alterar {
                background-color: #333333;
                color: #ffffff;
                border: 1px solid #444444;
                border-radius: 8px;
                padding: 5px 14px;
                font-weight: bold;
            }
            QPushButton#btn_alterar:hover {
                background-color: #444444;
            }
        """)

    def _montar_interface(self):
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(15, 15, 15, 15)
        layout_principal.setSpacing(10)

        # Cabeçalho
        lbl_titulo = QLabel("Conector Chip 7")
        lbl_titulo.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        lbl_sub = QLabel("Capture, extraia e gerencie conteúdos diretamente do Chip 7.")
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
        gb_captura = QGroupBox("🔗 Captura de Mídia - Chip 7")
        ly_captura = QVBoxLayout(gb_captura)
        ly_captura.setContentsMargins(10, 12, 10, 10)
        ly_captura.setSpacing(8)

        self.txt_url = QLineEdit()
        self.txt_url.setPlaceholderText("Cole o link do vídeo, aula ou curso aqui...")
        ly_captura.addWidget(self.txt_url)

        # Seleção de Qualidade
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

        # Botões de Ação com Cantos Arredondados
        ly_btns = QHBoxLayout()
        self.btn_avulso = QPushButton("⚡ Baixar Mídia Avulsa")
        self.btn_avulso.setStyleSheet("background-color: #0066cc; color: white; font-weight: bold; padding: 8px; border-radius: 8px; border: none;")
        
        self.btn_curso = QPushButton("🗺️ Mapear e Baixar Curso / Playlist")
        self.btn_curso.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; padding: 8px; border-radius: 8px; border: none;")
        
        ly_btns.addWidget(self.btn_avulso)
        ly_btns.addWidget(self.btn_curso)
        ly_captura.addLayout(ly_btns)

        ly_esq.addWidget(gb_captura)

        # 2. Autenticação
        gb_auth = QGroupBox("🔐 Autenticação (Áreas Pagas / Privadas)")
        form_auth = QFormLayout(gb_auth)
        form_auth.setContentsMargins(10, 12, 10, 10)
        form_auth.setSpacing(8)

        self.txt_email = QLineEdit()
        self.txt_email.setPlaceholderText("E-mail / Usuário")
        self.txt_senha = QLineEdit()
        self.txt_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_senha.setPlaceholderText("Senha")

        lbl_email = QLabel("E-mail / Usuário")
        lbl_email.setProperty("class", "lbl-box")
        lbl_senha = QLabel("Senha")
        lbl_senha.setProperty("class", "lbl-box")

        form_auth.addRow(lbl_email, self.txt_email)
        form_auth.addRow(lbl_senha, self.txt_senha)

        ly_esq.addWidget(gb_auth)

        # 3. Pasta de Destino
        gb_destino = QGroupBox("📁 Pasta de Destino")
        ly_dest = QHBoxLayout(gb_destino)
        ly_dest.setContentsMargins(10, 12, 10, 10)
        self.txt_destino = QLineEdit(os.path.join(os.path.expanduser("~"), "Downloads", "PRT_Nexus"))
        self.btn_alterar_dest = QPushButton("Alterar")
        self.btn_alterar_dest.setObjectName("btn_alterar")
        ly_dest.addWidget(self.txt_destino)
        ly_dest.addWidget(self.btn_alterar_dest)

        ly_esq.addWidget(gb_destino)

        layout_top.addLayout(ly_esq, stretch=1)

        # ================= COLUNA DIREITA =================
        gb_org = QGroupBox("📁 Organização de Pastas (Curso / Playlist)")
        form_org = QFormLayout(gb_org)
        form_org.setContentsMargins(10, 12, 10, 10)
        form_org.setSpacing(12)

        lbl_nome_cnt = QLabel("Nome do Conteúdo")
        lbl_nome_cnt.setProperty("class", "lbl-box")
        self.txt_nome_conteudo = QLineEdit("Chip 7 - Curso Extraído")
        
        lbl_est = QLabel("Estrutura")
        lbl_est.setProperty("class", "lbl-box")
        self.txt_estrutura = QLineEdit("Organizado Automaticamente por Módulo")
        self.txt_estrutura.setReadOnly(True)

        lbl_mid = QLabel("Mídias")
        lbl_mid.setProperty("class", "lbl-box")
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
        self.lbl_status_global.setStyleSheet("""
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

        ly_prog_geral.addWidget(self.lbl_status_global, stretch=1)
        ly_prog_geral.addWidget(self.pbar_global, stretch=2)
        layout_principal.addLayout(ly_prog_geral)

        # ================= TABELA DE MÍDIAS =================
        gb_tabela = QGroupBox("📦 Mídias Concluídas do Chip 7")
        ly_tab = QVBoxLayout(gb_tabela)
        ly_tab.setContentsMargins(10, 12, 10, 10)

        self.tabela = QTableWidget(0, 4)
        self.tabela.setHorizontalHeaderLabels(["#", "Título / Nome do Arquivo", "Caminho Salvo", "Status"])
        
        header = self.tabela.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        
        # Largura enxuta para a 1ª coluna (#) e largura expandida para Status (220px)
        self.tabela.setColumnWidth(0, 45)
        self.tabela.setColumnWidth(3, 220)

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

        self.worker = Chip7Worker(url, email, senha, destino, modo_avulso=modo_avulso)
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

    def _on_concluido(self, sucesso, mensagem):
        self.btn_avulso.setEnabled(True)
        self.btn_curso.setEnabled(True)

        if sucesso:
            QMessageBox.information(self, "Chip 7", mensagem)
        else:
            QMessageBox.critical(self, "Chip 7 - Erro", mensagem)