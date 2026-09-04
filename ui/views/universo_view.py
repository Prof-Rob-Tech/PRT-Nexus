import os
import re
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QLineEdit, 
    QPushButton, QMessageBox, QTableWidget, QTableWidgetItem, QProgressBar, QHeaderView
)
from services.extractors.universo_mapper import UniversoWorker

class UniversoView(QWidget):
    def __init__(self, parent=None, downloads_view=None):
        super().__init__(parent)
        self.downloads_view = downloads_view
        self.worker = None
        self._lbl_status = None

        self._montar_interface()
        self._conectar_acoes()

    def _montar_interface(self):
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(15, 15, 15, 15)
        layout_principal.setSpacing(12)

        # Cabeçalho
        lbl_titulo = QLabel("Conector Universo Técnico")
        lbl_titulo.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        lbl_sub = QLabel("Capture, extraia e gerencie conteúdos diretamente do Universo Técnico.")
        lbl_sub.setStyleSheet("font-size: 11px; color: #888888;")
        layout_principal.addWidget(lbl_titulo)
        layout_principal.addWidget(lbl_sub)

        # Área de Inputs
        layout_top = QHBoxLayout()
        
        # Grupo Esquerdo - Captura
        gb_captura = QGroupBox("Captura de Mídia - Universo Técnico")
        ly_captura = QVBoxLayout(gb_captura)
        
        self.txt_url = QLineEdit()
        self.txt_url.setPlaceholderText("https://universotecnico.com/cursos-ead/aula/...")
        ly_captura.addWidget(self.txt_url)

        ly_btns = QHBoxLayout()
        self.btn_avulso = QPushButton("⚡ Baixar Mídia Avulsa")
        self.btn_avulso.setStyleSheet("background-color: #0066cc; color: white; font-weight: bold; padding: 6px;")
        
        self.btn_curso = QPushButton("🗺️ Mapear e Baixar Curso / Playlist")
        self.btn_curso.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; padding: 6px;")
        
        ly_btns.addWidget(self.btn_avulso)
        ly_btns.addWidget(self.btn_curso)
        ly_captura.addLayout(ly_btns)

        # Grupo Autenticação
        gb_auth = QGroupBox("Autenticação (Áreas Pagas / Privadas)")
        ly_auth = QVBoxLayout(gb_auth)
        self.txt_email = QLineEdit()
        self.txt_email.setPlaceholderText("E-mail / Usuário")
        self.txt_senha = QLineEdit()
        self.txt_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_senha.setPlaceholderText("Senha")
        ly_auth.addWidget(self.txt_email)
        ly_auth.addWidget(self.txt_senha)

        # Grupo Destino
        gb_destino = QGroupBox("Pasta de Destino")
        ly_dest = QHBoxLayout(gb_destino)
        self.txt_destino = QLineEdit(os.path.join(os.path.expanduser("~"), "Downloads", "PRT_Nexus"))
        btn_alterar = QPushButton("Alterar")
        ly_dest.addWidget(self.txt_destino)
        ly_dest.addWidget(btn_alterar)

        ly_esq = QVBoxLayout()
        ly_esq.addWidget(gb_captura)
        ly_esq.addWidget(gb_auth)
        ly_esq.addWidget(gb_destino)
        layout_top.addLayout(ly_esq, stretch=2)

        # Grupo Direito - Organização
        gb_org = QGroupBox("Organização de Pastas (Curso / Playlist)")
        ly_org = QVBoxLayout(gb_org)
        ly_org.addWidget(QLabel("Nome do Conteúdo: Universo Técnico - Curso Extraído"))
        ly_org.addWidget(QLabel("Estrutura: Organizado Automaticamente por Módulo"))
        ly_org.addWidget(QLabel("Mídias: Extração Sequencial de Vídeos"))
        layout_top.addWidget(gb_org, stretch=1)

        layout_principal.addLayout(layout_top)

        # Progresso Geral
        self.lbl_status_global = QLabel("Aguardando início...")
        self.lbl_status_global.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        self.pbar_global = QProgressBar()
        self.pbar_global.setRange(0, 100)
        self.pbar_global.setValue(0)
        self.pbar_global.setStyleSheet("""
            QProgressBar {
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                text-align: center;
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #2ecc71;
            }
        """)

        layout_principal.addWidget(self.lbl_status_global)
        layout_principal.addWidget(self.pbar_global)

        # Tabela de Mídias
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

        # Limpeza do título na exibição da tabela
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

            # Coluna 0 (#): Número centralizado
            item_num = QTableWidgetItem(num)
            item_num.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tabela.setItem(row, 0, item_num)

            # Coluna 1: Título
            self.tabela.setItem(row, 1, QTableWidgetItem(titulo_exibicao))

            # Coluna 2: Caminho
            self.tabela.setItem(row, 2, QTableWidgetItem(caminho))

            # Coluna 3: Barra de progresso individual
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