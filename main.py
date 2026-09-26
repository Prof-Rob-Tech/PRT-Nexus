"""
===========================================================
PRT Nexus - Ponto de Entrada Principal
===========================================================
"""

import os
import sys

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import QApplication

# Configurações essenciais do motor WebEngine (Chromium / OpenGL)
QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
os.environ["QTWEBENGINE_DISABLE_SANDBOX"] = "1"

from database.manager import db_manager
from theme.colors import PALETAS, ThemeColors, repintar
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    chave = db_manager.get_setting("tema", "slate")
    if chave not in PALETAS:
        chave = "slate"
    origem = ThemeColors.paleta()
    ThemeColors.aplicar(chave)

    window = MainWindow()
    if chave != "slate":
        repintar(origem, ThemeColors.paleta())
        window.sincronizar_tema()
    window.showMaximized()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()