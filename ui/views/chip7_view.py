import os
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
        
        # Alterar textos da interface para "Chip 7"
        self._customizar_interface()
        
        # Reconectar botões para o backend do Chip 7
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

        for btn in self.findChildren(QPushButton):
            if "baixar" in btn.text().lower() or "mapear" in btn.text().lower():
                btn.setEnabled(False)

        self.worker = Chip7Worker(url, email, senha, destino, modo_avulso=modo_avulso)
        self.worker.progresso.connect(self._on_progresso)
        self.worker.item_concluido.connect(self._on_item_concluido)
        self.worker.concluido.connect(self._on_concluido)
        self.worker.start()

    def _on_progresso(self, msg, pct):
        pbar = self.findChild(QProgressBar)
        if pbar:
            pbar.setValue(pct)
            
        for lbl in self.findChildren(QLabel):
            if any(term in lbl.text().lower() for term in ["aguardando", "iniciando", "processando", "acessando", "downloads"]):
                lbl.setText(msg)
                break

    def _on_item_concluido(self, item):
        tabela = self.findChild(QTableWidget)
        if not tabela:
            return
        row = tabela.rowCount()
        tabela.insertRow(row)
        tabela.setItem(row, 0, QTableWidgetItem(str(item.get("num", ""))))
        tabela.setItem(row, 1, QTableWidgetItem(str(item.get("titulo", ""))))
        tabela.setItem(row, 2, QTableWidgetItem(str(item.get("caminho", ""))))
        tabela.setItem(row, 3, QTableWidgetItem(str(item.get("status", ""))))

    def _on_concluido(self, sucesso, mensagem):
        for btn in self.findChildren(QPushButton):
            if "baixar" in btn.text().lower() or "mapear" in btn.text().lower():
                btn.setEnabled(True)

        if sucesso:
            QMessageBox.information(self, "Chip 7", mensagem)
        else:
            QMessageBox.critical(self, "Chip 7 - Erro", mensagem)