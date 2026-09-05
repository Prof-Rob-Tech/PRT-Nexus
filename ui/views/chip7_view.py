import os
from PySide6.QtWidgets import QLabel, QGroupBox, QLineEdit, QMessageBox
from ui.views.universo_view import UniversoView
from services.extractors.chip7_connector import Chip7Worker

class Chip7View(UniversoView):
    def __init__(self, parent=None, downloads_view=None):
        super().__init__(parent=parent, downloads_view=downloads_view)
        self._customizar_interface()

    def _customizar_interface(self):
        # Altera apenas as referências de texto da tela pai para Chip 7
        for lbl in self.findChildren(QLabel):
            if "Universo Técnico" in lbl.text():
                lbl.setText(lbl.text().replace("Universo Técnico", "Chip 7"))

        for group in self.findChildren(QGroupBox):
            if "Universo Técnico" in group.title():
                group.setTitle(group.title().replace("Universo Técnico", "Chip 7"))

        for le in self.findChildren(QLineEdit):
            if "Universo Técnico" in le.placeholderText():
                le.setPlaceholderText(le.placeholderText().replace("Universo Técnico", "Chip 7"))

    def _iniciar_download(self, modo_avulso):
        # Leitura direta das variáveis herdadas do UniversoView
        url = self.txt_url.text().strip()
        email = self.txt_email.text().strip()
        senha = self.txt_senha.text().strip()
        destino = self.txt_destino.text().strip()

        if not url or not email or not senha:
            QMessageBox.warning(self, "Campos Vazios", "Preencha o Link, E-mail e Senha do Chip 7 antes de iniciar!")
            return

        self.tabela.setRowCount(0)
        self._configurar_estilo_tabela(self.tabela)

        self.btn_avulso.setEnabled(False)
        self.btn_curso.setEnabled(False)

        # Instancia o worker específico do Chip 7 e reaproveita todos os callbacks da tela pai
        self.worker = Chip7Worker(url, email, senha, destino, modo_avulso=modo_avulso)
        self.worker.progresso.connect(self._on_progresso)
        self.worker.item_progresso.connect(self._on_item_progresso)
        self.worker.item_concluido.connect(self._on_item_concluido)
        self.worker.concluido.connect(self._on_concluido)
        self.worker.start()