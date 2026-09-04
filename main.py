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

from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()