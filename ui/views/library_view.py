"""
===========================================================
PRT Nexus - Library View
Class: LibraryView
Description: Lista as mídias salvas em Downloads/PRT_Nexus.
===========================================================
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from database.manager import db_manager
from theme.colors import ThemeColors

EXTENSOES = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".m4v", ".mp3", ".m4a", ".wav"}


def pasta_da_biblioteca() -> Path:
    return Path(os.path.expanduser("~")) / "Downloads" / "PRT_Nexus"


def tamanho_legivel(nbytes: int) -> str:
    if nbytes >= 1024 * 1024 * 1024:
        return f"{nbytes / (1024 * 1024 * 1024):.1f} GB"
    if nbytes >= 1024 * 1024:
        return f"{nbytes / (1024 * 1024):.1f} MB"
    if nbytes >= 1024:
        return f"{nbytes / 1024:.0f} KB"
    return f"{nbytes} B"


class LibraryView(QWidget):
    """Mídias baixadas pelos conectores e pelo navegador."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._itens: list[dict] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        header_layout = QHBoxLayout()
        title_layout = QVBoxLayout()
        title_layout.setSpacing(4)

        lbl_title = QLabel("📁  Biblioteca de Mídias")
        lbl_title.setStyleSheet(
            f"font-size: 20px; font-weight: bold; color: {ThemeColors.TEXT}; background: transparent;"
        )
        lbl_subtitle = QLabel("Gerencie e visualize todas as mídias salvas localmente no computador.")
        lbl_subtitle.setStyleSheet(
            f"font-size: 13px; color: {ThemeColors.TEXT_SECONDARY}; background: transparent;"
        )
        title_layout.addWidget(lbl_title)
        title_layout.addWidget(lbl_subtitle)
        header_layout.addLayout(title_layout, stretch=1)

        self.btn_limpar = QPushButton("Limpar Biblioteca")
        self.btn_limpar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_limpar.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {ThemeColors.TEXT_SECONDARY};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
                padding: 8px 14px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                border-color: #EF4444;
                color: #EF4444;
            }}
        """)
        self.btn_limpar.clicked.connect(self._limpar)
        header_layout.addWidget(self.btn_limpar)

        self.btn_pasta = QPushButton("📁  Abrir Pasta no Windows")
        self.btn_pasta.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pasta.setStyleSheet(f"""
            QPushButton {{
                background-color: {ThemeColors.CARD};
                color: {ThemeColors.TEXT};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
                padding: 8px 14px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                border-color: {ThemeColors.PRIMARY};
            }}
        """)
        self.btn_pasta.clicked.connect(self._abrir_pasta_raiz)
        header_layout.addWidget(self.btn_pasta)
        main_layout.addLayout(header_layout)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Pesquisar mídias na biblioteca...")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {ThemeColors.CARD};
                color: {ThemeColors.TEXT};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {ThemeColors.PRIMARY};
            }}
        """)
        self.search_input.textChanged.connect(self._filtrar)
        main_layout.addWidget(self.search_input)

        self.container_frame = QFrame()
        self.container_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {ThemeColors.CARD};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
            }}
        """)
        self.container_layout = QVBoxLayout(self.container_frame)
        self.container_layout.setContentsMargins(20, 20, 20, 20)

        self.empty_widget = QWidget()
        self.empty_widget.setStyleSheet("background: transparent; border: none;")
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(10)

        lbl_empty_icon = QLabel("🎬")
        lbl_empty_icon.setStyleSheet("font-size: 36px; background: transparent; border: none;")
        lbl_empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_empty_title = QLabel("Sua biblioteca está vazia")
        lbl_empty_title.setStyleSheet(f"""
            font-size: 16px;
            font-weight: bold;
            color: {ThemeColors.TEXT};
            background: transparent;
            border: none;
        """)
        lbl_empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_empty_desc = QLabel(
            "Os vídeos e conteúdos baixados através dos conectores e do navegador aparecerão listados aqui."
        )
        lbl_empty_desc.setStyleSheet(f"""
            font-size: 13px;
            color: {ThemeColors.TEXT_SECONDARY};
            background: transparent;
            border: none;
        """)
        lbl_empty_desc.setWordWrap(True)
        lbl_empty_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_empty_desc.setMaximumWidth(640)

        empty_layout.addStretch()
        empty_layout.addWidget(lbl_empty_icon)
        empty_layout.addWidget(lbl_empty_title)
        empty_layout.addWidget(lbl_empty_desc)
        empty_layout.addStretch()
        self.container_layout.addWidget(self.empty_widget)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("border: none; background: transparent;")
        self.cards_container = QWidget()
        self.cards_container.setStyleSheet("background: transparent;")
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setSpacing(10)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.cards_container)
        self.container_layout.addWidget(self.scroll_area)
        self.scroll_area.setVisible(False)

        main_layout.addWidget(self.container_frame, stretch=1)
        self.carregar()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.carregar()

    def carregar(self) -> None:
        self._itens = self._ler_midias()
        self._filtrar(self.search_input.text())

    def _ler_midias(self) -> list[dict]:
        itens: list[dict] = []
        conhecidos: set[str] = set()
        escondidos = db_manager.hidden_library_paths()
        raiz = pasta_da_biblioteca()

        if raiz.exists():
            for arquivo in raiz.rglob("*"):
                if not arquivo.is_file() or arquivo.suffix.lower() not in EXTENSOES:
                    continue
                if arquivo.stat().st_size <= 0:
                    continue
                caminho = str(arquivo.resolve())
                if caminho.lower() in escondidos:
                    continue
                conhecidos.add(caminho.lower())
                itens.append(self._item_do_arquivo(arquivo, raiz))

        for registro in db_manager.get_all_downloads() or []:
            caminho = str(registro.get("file_path") or "")
            if not caminho or caminho.lower() in conhecidos or caminho.lower() in escondidos:
                continue
            arquivo = Path(caminho)
            if not arquivo.is_file() or arquivo.suffix.lower() not in EXTENSOES:
                continue
            conhecidos.add(str(arquivo.resolve()).lower())
            itens.append({
                "title": registro.get("title") or arquivo.stem,
                "platform": registro.get("platform") or "Local",
                "file_path": str(arquivo),
                "size": tamanho_legivel(arquivo.stat().st_size),
                "when": datetime.fromtimestamp(arquivo.stat().st_mtime).strftime("%d/%m/%Y %H:%M"),
                "mtime": arquivo.stat().st_mtime,
            })

        itens.sort(key=lambda item: item["mtime"], reverse=True)
        return itens

    def _item_do_arquivo(self, arquivo: Path, raiz: Path) -> dict:
        try:
            relativo = arquivo.relative_to(raiz)
            plataforma = relativo.parts[0] if len(relativo.parts) > 1 else "PRT Nexus"
        except ValueError:
            plataforma = "Local"
        modificado = arquivo.stat().st_mtime
        return {
            "title": arquivo.stem,
            "platform": plataforma,
            "file_path": str(arquivo),
            "size": tamanho_legivel(arquivo.stat().st_size),
            "when": datetime.fromtimestamp(modificado).strftime("%d/%m/%Y %H:%M"),
            "mtime": modificado,
        }

    def _filtrar(self, texto: str) -> None:
        consulta = texto.strip().lower()
        if not consulta:
            self._mostrar(self._itens)
            return
        filtrados = [
            item for item in self._itens
            if consulta in item["title"].lower()
            or consulta in item["platform"].lower()
            or consulta in item["file_path"].lower()
        ]
        self._mostrar(filtrados)

    def _mostrar(self, itens: list[dict]) -> None:
        while self.cards_layout.count():
            child = self.cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not itens:
            self.empty_widget.setVisible(True)
            self.scroll_area.setVisible(False)
            return

        self.empty_widget.setVisible(False)
        self.scroll_area.setVisible(True)

        for item in itens:
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {ThemeColors.BACKGROUND};
                    border: 1px solid {ThemeColors.BORDER};
                    border-radius: 6px;
                }}
            """)
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(12, 8, 12, 8)

            info_layout = QVBoxLayout()
            info_layout.setSpacing(2)
            lbl_title = QLabel(f"🎬  {item['title']}")
            lbl_title.setStyleSheet(
                f"font-size: 14px; font-weight: bold; color: {ThemeColors.TEXT}; border: none; background: transparent;"
            )
            lbl_meta = QLabel(f"{item['platform']}  •  {item['size']}  •  {item['when']}")
            lbl_meta.setStyleSheet(
                f"font-size: 12px; color: {ThemeColors.TEXT_SECONDARY}; border: none; background: transparent;"
            )
            info_layout.addWidget(lbl_title)
            info_layout.addWidget(lbl_meta)
            card_layout.addLayout(info_layout, stretch=1)

            btn_abrir = QPushButton("▶ Abrir")
            btn_abrir.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_abrir.setStyleSheet(f"""
                QPushButton {{
                    background-color: {ThemeColors.PRIMARY};
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-weight: bold;
                }}
            """)
            caminho = item["file_path"]
            btn_abrir.clicked.connect(lambda _, p=caminho: self._abrir_arquivo(p))

            btn_folder = QPushButton("📁 Pasta")
            btn_folder.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_folder.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {ThemeColors.TEXT};
                    border: 1px solid {ThemeColors.BORDER};
                    border-radius: 4px;
                    padding: 6px 10px;
                }}
                QPushButton:hover {{
                    border-color: {ThemeColors.PRIMARY};
                }}
            """)
            btn_folder.clicked.connect(lambda _, p=caminho: self._abrir_pasta_do_arquivo(p))

            card_layout.addWidget(btn_abrir)
            card_layout.addWidget(btn_folder)
            self.cards_layout.addWidget(card)

    def _limpar(self) -> None:
        if not self._itens and not db_manager.get_all_downloads():
            return
        resposta = QMessageBox.question(
            self,
            "Limpar Biblioteca",
            "Tirar os registros da biblioteca?\nOs vídeos na pasta não são apagados.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resposta != QMessageBox.StandardButton.Yes:
            return
        db_manager.hide_library_paths([item["file_path"] for item in self._itens])
        db_manager.clear_downloads()
        self.carregar()

    def _abrir_pasta_raiz(self) -> None:
        pasta = pasta_da_biblioteca()
        pasta.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(pasta.resolve())))

    def _abrir_arquivo(self, caminho: str) -> None:
        arquivo = Path(caminho)
        if not arquivo.is_file():
            QMessageBox.warning(self, "Aviso", f"O arquivo não foi localizado em:\n{caminho}")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(arquivo.resolve())))

    def _abrir_pasta_do_arquivo(self, caminho: str) -> None:
        arquivo = Path(caminho)
        if not arquivo.exists():
            QMessageBox.warning(self, "Aviso", f"A pasta ou o arquivo não existe em:\n{caminho}")
            return
        if sys.platform == "win32":
            subprocess.Popen(f'explorer /select,"{arquivo.resolve()}"')
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(arquivo.parent.resolve())))
