import os

from PySide6.QtCore import QEvent, QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QComboBox,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QCheckBox,
)

from services.extractors.drive_connector import DriveWorker, separar_links


class DriveView(QWidget):
    def __init__(self, parent=None, downloads_view=None):
        super().__init__(parent)
        self.downloads_view = downloads_view
        self.worker = None
        self._montar_interface()
        self._aplicar_estilos()
        self._conectar_acoes()

    def _aplicar_estilos(self):
        self.setStyleSheet("""
            QWidget { background-color: #1e1e1e; color: #ffffff; }
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
            QLineEdit, QPlainTextEdit, QComboBox {
                background-color: #252526;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                color: #ffffff;
                padding: 6px 10px;
                font-size: 12px;
            }
            QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border: 1px solid #0066cc; }
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
            QPushButton#btn_alterar, QPushButton#btn_pausar, QPushButton#btn_cancelar, QPushButton#btn_limpar {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 5px 12px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton#btn_cancelar:hover, QPushButton#btn_limpar:hover { background-color: #8b0000; }
        """)

    def _montar_interface(self):
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(15, 15, 15, 15)
        layout_principal.setSpacing(10)

        lbl_titulo = QLabel("Conector Google Drive")
        lbl_titulo.setStyleSheet("font-size: 24px; font-weight: bold; color: #ffffff;")
        lbl_sub = QLabel("Cole um ou mais links públicos, um por linha. A fila baixa na ordem, com o nome original.")
        lbl_sub.setStyleSheet("font-size: 14px; color: #888888;")
        layout_principal.addWidget(lbl_titulo)
        layout_principal.addWidget(lbl_sub)

        layout_top = QHBoxLayout()
        layout_top.setSpacing(12)
        ly_esq = QVBoxLayout()
        ly_esq.setSpacing(10)

        gb_captura = QGroupBox("🔗 Links públicos do Drive")
        ly_captura = QVBoxLayout(gb_captura)
        ly_captura.setContentsMargins(10, 10, 10, 10)
        ly_captura.setSpacing(8)
        self.txt_url = QPlainTextEdit()
        self.txt_url.setPlaceholderText("Um link por linha\nhttps://drive.google.com/drive/folders/...\nhttps://drive.google.com/file/d/...")
        self.txt_url.setFixedHeight(78)
        ly_captura.addWidget(self.txt_url)
        self.btn_baixar = QPushButton("📥 Listar e baixar a fila")
        self.btn_baixar.setStyleSheet(
            "background-color: #1A73E8; color: white; font-weight: bold; padding: 8px; border-radius: 8px; border: none;"
        )
        ly_captura.addWidget(self.btn_baixar)
        ly_esq.addWidget(gb_captura)

        gb_destino = QGroupBox("📁 Pasta de Destino")
        ly_dest = QHBoxLayout(gb_destino)
        ly_dest.setContentsMargins(10, 10, 10, 10)
        self.txt_destino = QLineEdit(os.path.join(os.path.expanduser("~"), "Downloads", "PRT_Nexus"))
        self.txt_destino.deselect()
        self.txt_destino.installEventFilter(self)
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

        lbl_nome = QLabel("Nome do Conteúdo")
        lbl_nome.setProperty("class", "lbl-box")
        self.txt_nome_conteudo = QLineEdit()
        self.txt_nome_conteudo.setPlaceholderText("Vazio usa o nome do Drive. Com vários links, cada um fica na própria pasta.")

        lbl_est = QLabel("Estrutura")
        lbl_est.setProperty("class", "lbl-box")
        self.cmb_estrutura = QComboBox()
        self.cmb_estrutura.addItems([
            "Manter subpastas do Drive",
            "Todos os arquivos na mesma pasta",
        ])

        lbl_mid = QLabel("Mídias")
        lbl_mid.setProperty("class", "lbl-box")
        self.cmb_midias = QComboBox()
        self.cmb_midias.addItems([
            "Todos os arquivos",
            "Só vídeos",
            "Só documentos",
        ])
        form_org.addRow(lbl_nome, self.txt_nome_conteudo)
        form_org.addRow(lbl_est, self.cmb_estrutura)
        form_org.addRow(lbl_mid, self.cmb_midias)
        ly_dir.addWidget(gb_org)

        gb_opcoes = QGroupBox("⚙️ Opções")
        ly_opcoes = QVBoxLayout(gb_opcoes)
        ly_opcoes.setContentsMargins(12, 12, 12, 12)
        self.chk_notif = QCheckBox("Notificar com som ao concluir")
        ly_opcoes.addWidget(self.chk_notif)
        ly_dir.addWidget(gb_opcoes)
        layout_top.addLayout(ly_dir, stretch=1)
        layout_principal.addLayout(layout_top)

        ly_prog = QHBoxLayout()
        self.lbl_status_global = QLabel("Aguardando link do Drive...")
        self.lbl_status_global.setStyleSheet(
            "background-color: #1e1e1e; border: 1px solid #3a3a3a; border-radius: 8px; color: #aaaaaa; font-size: 11px; padding: 5px 10px;"
        )
        self.lbl_velocidade = QLabel("-- MiB/s | ETA: --:--")
        self.lbl_velocidade.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_velocidade.setStyleSheet(
            "background-color: #1e1e1e; border: 1px solid #3a3a3a; border-radius: 8px; color: #aaaaaa; font-size: 11px; padding: 5px 10px;"
        )
        self.pbar_global = QProgressBar()
        self.pbar_global.setRange(0, 100)
        self.pbar_global.setValue(0)
        self.pbar_global.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pbar_global.setStyleSheet("""
            QProgressBar {
                border: 1px solid #3a3a3a; border-radius: 8px; text-align: center;
                background-color: #1e1e1e; color: #ffffff; font-size: 11px;
            }
            QProgressBar::chunk { background-color: #1A73E8; border-radius: 6px; }
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
        layout_principal.addLayout(ly_prog)

        gb_tabela = QFrame()
        gb_tabela.setObjectName("gb_tabela")
        ly_tab = QVBoxLayout(gb_tabela)
        ly_tab.setContentsMargins(10, 8, 10, 8)
        ly_tab.setSpacing(6)

        ly_topo = QHBoxLayout()
        ly_topo.setContentsMargins(0, 0, 0, 0)
        ly_topo.setSpacing(8)
        lbl_tab = QLabel("📦 Arquivos do Drive (duplo clique abre a pasta)")
        lbl_tab.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #ffffff; background: transparent; border: none; padding: 0;"
        )
        lbl_tab.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.btn_limpar = QPushButton("🗑️ Limpar Concluídos")
        self.btn_limpar.setObjectName("btn_limpar")
        ly_topo.addWidget(lbl_tab, 1, Qt.AlignmentFlag.AlignVCenter)
        ly_topo.addWidget(self.btn_limpar, 0, Qt.AlignmentFlag.AlignVCenter)
        ly_tab.addLayout(ly_topo)

        self.tabela = QTableWidget(0, 4)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setHorizontalHeaderLabels(["#", "Arquivo", "Caminho Salvo", "Status"])
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

    def showEvent(self, event):
        super().showEvent(event)
        self.txt_destino.deselect()

    def eventFilter(self, obj, event):
        if obj is self.txt_destino and event.type() == QEvent.Type.FocusIn:
            QTimer.singleShot(0, self.txt_destino.deselect)
        return super().eventFilter(obj, event)

    def _conectar_acoes(self):
        self.btn_baixar.clicked.connect(self._iniciar_download)
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
            self.btn_baixar.setEnabled(True)
            self.btn_pausar.setEnabled(False)
            self.btn_cancelar.setEnabled(False)
            self.btn_pausar.setText("⏸️ Pausar")

    def _limpar_concluidos(self):
        em_andamento = bool(self.worker and self.worker.isRunning())
        for row in reversed(range(self.tabela.rowCount())):
            pbar = self.tabela.cellWidget(row, 3)
            if not isinstance(pbar, QProgressBar):
                continue
            if pbar.value() >= 100 or not em_andamento:
                self.tabela.removeRow(row)

    def _remover_linhas_incompletas(self):
        for row in reversed(range(self.tabela.rowCount())):
            pbar = self.tabela.cellWidget(row, 3)
            if isinstance(pbar, QProgressBar) and pbar.value() < 100:
                self.tabela.removeRow(row)

    def _iniciar_download(self):
        links = separar_links(self.txt_url.toPlainText())
        destino = self.txt_destino.text().strip()
        if not links:
            QMessageBox.warning(self, "Link vazio", "Cole um ou mais links públicos do Drive, um por linha.")
            return
        self.txt_destino.deselect()
        self.tabela.setRowCount(0)
        self._configurar_estilo_tabela(self.tabela)
        self.btn_baixar.setEnabled(False)
        self.btn_pausar.setEnabled(True)
        self.btn_cancelar.setEnabled(True)
        self.btn_pausar.setText("⏸️ Pausar")
        self.lbl_velocidade.setText("-- MiB/s | ETA: --:--")
        opcoes = {
            "nome_conteudo": self.txt_nome_conteudo.text().strip(),
            "estrutura": self.cmb_estrutura.currentText(),
            "midias": self.cmb_midias.currentText(),
        }
        self.worker = DriveWorker("", destino, opcoes=opcoes, urls=links)
        self.worker.progresso.connect(self._on_progresso)
        self.worker.velocidade.connect(self.lbl_velocidade.setText)
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
                border: 1px solid #3a3a3a; border-radius: 6px; text-align: center;
                background-color: #1e1e1e; color: #ffffff; font-size: 11px; font-weight: bold;
            }
            QProgressBar::chunk { background-color: #2ecc71; border-radius: 4px; }
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
        titulo = str(item.get("titulo", ""))
        caminho = str(item.get("caminho", ""))
        status = str(item.get("status", ""))
        linha = -1
        for row in range(self.tabela.rowCount()):
            item_num = self.tabela.item(row, 0)
            if item_num and item_num.text() == num:
                linha = row
                break
        if linha >= 0:
            pbar = self.tabela.cellWidget(linha, 3)
            if isinstance(pbar, QProgressBar) and status == "Concluído":
                pbar.setValue(100)
                pbar.setFormat("Concluído (100%)")
            elif isinstance(pbar, QProgressBar) and status == "Erro":
                pbar.setValue(100)
                pbar.setFormat("Erro")
            return
        row = self.tabela.rowCount()
        self.tabela.insertRow(row)
        item_num = QTableWidgetItem(num)
        item_num.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tabela.setItem(row, 0, item_num)
        self.tabela.setItem(row, 1, QTableWidgetItem(titulo))
        self.tabela.setItem(row, 2, QTableWidgetItem(caminho))
        pbar = self._criar_barra_status()
        if status == "Concluído":
            pbar.setValue(100)
            pbar.setFormat("Concluído (100%)")
        else:
            pbar.setFormat("%p%")
        self.tabela.setCellWidget(row, 3, pbar)

    def _on_concluido(self, sucesso, mensagem):
        self.btn_baixar.setEnabled(True)
        self.btn_pausar.setEnabled(False)
        self.btn_cancelar.setEnabled(False)
        if self.chk_notif.isChecked():
            from PySide6.QtWidgets import QApplication
            QApplication.beep()
        if sucesso:
            QMessageBox.information(self, "Google Drive", mensagem)
        else:
            QMessageBox.critical(self, "Google Drive", mensagem)
