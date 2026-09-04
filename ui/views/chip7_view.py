import os
import re
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel, QGroupBox, QLineEdit, QPushButton, 
    QMessageBox, QTableWidget, QTableWidgetItem, QProgressBar
)
from ui.views.universo_view import UniversoView
from services.extractors.chip7_connector import Chip7Worker

class Chip7View(UniversoView):
    def __init__(self, parent=None, downloads_view=None):
        super().__init__(parent=parent, downloads_view=downloads_view)
        self.worker = None
        self._lbl_status = None
        
        self._customizar_interface()
        self._conectar_acoes()

    def _customizar_interface(self):
        for lbl in self.findChildren(QLabel):
            if "Universo Técnico" in lbl.text():
                lbl.setText(lbl.text().replace("Universo Técnico", "Chip 7"))

        for group in self.findChildren(QGroupBox):
            if "Universo Técnico" in group.title():
                group.setTitle(group.title().replace("Universo Técnico", "Chip 7"))

        for le in self.findChildren(QLineEdit):
            if "Universo Técnico" in le.placeholderText():
                le.setPlaceholderText(le.placeholderText().replace("Universo Técnico", "Chip 7"))

        tabela = self.findChild(QTableWidget)
        if tabela:
            self._configurar_estilo_tabela(tabela)

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
        for btn in self.findChildren(QPushButton):
            txt = btn.text().lower()
            if "baixar" in txt or "mapear" in txt:
                try:
                    btn.clicked.disconnect()
                except Exception:
                    pass
                
                is_avulso = "avulsa" in txt
                btn.clicked.connect(lambda checked=False, a=is_avulso: self._iniciar_download_chip7(a))

    def _capturar_inputs(self):
        url, email, senha, destino = "", "", "", ""
        
        for le in self.findChildren(QLineEdit):
            txt = le.text().strip()
            ph = le.placeholderText().lower()
            
            if le.echoMode() == QLineEdit.EchoMode.Password:
                senha = txt
            elif "http" in txt or "chip7" in txt or "cole o link" in ph:
                url = txt
            elif "@" in txt or "e-mail" in ph or "usuário" in ph or "usuario" in ph:
                email = txt
            elif "downloads" in txt.lower() or "downloads" in ph or ":\\" in txt or ":/" in txt:
                destino = txt

        if not destino:
            destino = os.path.join(os.path.expanduser("~"), "Downloads", "PRT_Nexus")

        return url, email, senha, destino

    def _iniciar_download_chip7(self, modo_avulso):
        url, email, senha, destino = self._capturar_inputs()

        if not url or not email or not senha:
            QMessageBox.warning(self, "Campos Vazios", "Preencha o Link, E-mail e Senha do Chip 7 antes de iniciar!")
            return

        tabela = self.findChild(QTableWidget)
        if tabela:
            tabela.setRowCount(0)
            self._configurar_estilo_tabela(tabela)

        for btn in self.findChildren(QPushButton):
            if "baixar" in btn.text().lower() or "mapear" in btn.text().lower():
                btn.setEnabled(False)

        self._lbl_status = None
        self.worker = Chip7Worker(url, email, senha, destino, modo_avulso=modo_avulso)
        self.worker.progresso.connect(self._on_progresso)
        self.worker.item_progresso.connect(self._on_item_progresso)
        self.worker.item_concluido.connect(self._on_item_concluido)
        self.worker.concluido.connect(self._on_concluido)
        self.worker.start()

    def _on_progresso(self, msg, pct):
        pbar = self.findChild(QProgressBar)
        if pbar:
            pbar.setValue(pct)
            
        if self._lbl_status:
            self._lbl_status.setText(msg)
        else:
            for lbl in self.findChildren(QLabel):
                txt = lbl.text().lower()
                if any(term in txt for term in ["mapeando", "aguardando", "iniciando", "processando", "acessando", "downloads", "baixando"]):
                    self._lbl_status = lbl
                    self._lbl_status.setText(msg)
                    break

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
        tabela = self.findChild(QTableWidget)
        if not tabela:
            return

        for row in range(tabela.rowCount()):
            item_num = tabela.item(row, 0)
            if item_num and item_num.text() == str(num_str):
                pbar = tabela.cellWidget(row, 3)
                if isinstance(pbar, QProgressBar):
                    pbar.setValue(int(pct))
                break

    def _on_item_concluido(self, item):
        tabela = self.findChild(QTableWidget)
        if not tabela:
            return

        num = str(item.get("num", ""))
        titulo_bruto = str(item.get("titulo", ""))
        caminho = str(item.get("caminho", ""))
        status = str(item.get("status", ""))

        # Limpeza total do título (sem números, traços ou underlines no início)
        titulo_exibicao = re.sub(r'^\d+[\s\-_]*', '', titulo_bruto)
        titulo_exibicao = re.sub(r'^[\s\-_]+', '', titulo_exibicao).replace('_', ' ').strip()

        linha_existente = -1
        for row in range(tabela.rowCount()):
            item_num = tabela.item(row, 0)
            if item_num and item_num.text() == num:
                linha_existente = row
                break

        if linha_existente >= 0:
            pbar = tabela.cellWidget(linha_existente, 3)
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
            row = tabela.rowCount()
            tabela.insertRow(row)

            item_num = QTableWidgetItem(num)
            item_num.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            tabela.setItem(row, 0, item_num)

            tabela.setItem(row, 1, QTableWidgetItem(titulo_exibicao))
            tabela.setItem(row, 2, QTableWidgetItem(caminho))

            pbar = self._criar_barra_status()
            if status == "Concluído":
                pbar.setValue(100)
                pbar.setFormat("Concluído (100%)")
            else:
                pbar.setValue(0)
                pbar.setFormat("%p%")

            tabela.setCellWidget(row, 3, pbar)
            tabela.setColumnWidth(0, 45)

    def _on_concluido(self, sucesso, mensagem):
        for btn in self.findChildren(QPushButton):
            if "baixar" in btn.text().lower() or "mapear" in btn.text().lower():
                btn.setEnabled(True)

        if sucesso:
            QMessageBox.information(self, "Chip 7", mensagem)
        else:
            QMessageBox.critical(self, "Chip 7 - Erro", mensagem)