"""
===========================================================
PRT Nexus - Library View
Class: LibraryView
Description: Gerenciamento e reprodução de mídias baixadas.
===========================================================
"""

import subprocess
import sys
from pathlib import Path
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database.manager import db_manager
from theme.colors import ThemeColors


class LibraryView(QWidget):
    """Interface para exibição e gerenciamento dos arquivos salvos."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # Cabeçalho
        header_layout = QHBoxLayout()
        header_label = QLabel("Biblioteca de Mídias")
        header_label.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {ThemeColors.TEXT};")
        header_layout.addWidget(header_label)

        header_layout.addStretch()

        btn_refresh = QPushButton("🔄 Atualizar")
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.setStyleSheet(f"""
            QPushButton {{
                background-color: {ThemeColors.CARD};
                color: {ThemeColors.TEXT};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                border-color: {ThemeColors.PRIMARY};
            }}
        """)
        btn_refresh.clicked.connect(self.load_library)
        header_layout.addWidget(btn_refresh)

        layout.addLayout(header_layout)

        # Tabela de Mídias
        self.table = QTableWidget(0, 4)

        # Numeração Sequencial Esquerda (1, 2, 3...)
        v_header = self.table.verticalHeader()
        v_header.setVisible(True)
        v_header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        v_header.setMinimumSectionSize(36)
        v_header.setFixedWidth(42)

        headers = [
            ("Título / Arquivo", Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            ("Plataforma", Qt.AlignmentFlag.AlignCenter),
            ("Status", Qt.AlignmentFlag.AlignCenter),
            ("Ações", Qt.AlignmentFlag.AlignCenter),
        ]

        for col, (title, alignment) in enumerate(headers):
            item = QTableWidgetItem(title)
            item.setTextAlignment(alignment)
            self.table.setHorizontalHeaderItem(col, item)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 130)
        
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 120)
        
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(3, 200)

        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {ThemeColors.CARD};
                border: 1px solid {ThemeColors.BORDER};
                gridline-color: {ThemeColors.BORDER};
                border-radius: 8px;
            }}
            QHeaderView::section {{
                background-color: {ThemeColors.BACKGROUND};
                color: {ThemeColors.TEXT_SECONDARY};
                padding: 8px 12px;
                border: none;
                font-weight: bold;
            }}
            QHeaderView::section:vertical {{
                background-color: {ThemeColors.BACKGROUND};
                color: {ThemeColors.TEXT_SECONDARY};
                padding: 0 4px;
                border: none;
                border-right: 1px solid {ThemeColors.BORDER};
                font-weight: bold;
                text-align: center;
            }}
        """)

        layout.addWidget(self.table)
        self.load_library()

    def showEvent(self, event) -> None:
        """Atualiza a lista automaticamente ao alternar para a aba."""
        super().showEvent(event)
        self.load_library()

    def load_library(self) -> None:
        """Carrega os registros do banco e faz varredura na pasta local de downloads."""
        self.table.setRowCount(0)
        
        # 1. Carregar registros do banco de dados
        raw_items = db_manager.get_all_downloads() or []
        items = list(raw_items)
        
        known_paths = set()
        for item in items:
            p = item.get("file_path") if isinstance(item, dict) else getattr(item, "file_path", "")
            if p:
                known_paths.add(str(Path(p).resolve()))

        # 2. Varredura automática no diretório de downloads local
        media_extensions = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv", ".ts", ".mp3", ".m4a", ".wav"}
        downloads_dirs = [Path("downloads"), Path.home() / "Downloads"]

        for d_dir in downloads_dirs:
            if d_dir.exists():
                for file_path in d_dir.rglob("*"):
                    if file_path.is_file() and file_path.suffix.lower() in media_extensions:
                        resolved_path = str(file_path.resolve())
                        if resolved_path not in known_paths:
                            items.append({
                                "title": file_path.name,
                                "platform": "Local",
                                "status": "Concluído",
                                "file_path": str(file_path)
                            })
                            known_paths.add(resolved_path)

        # 3. Preencher a tabela
        for row, item in enumerate(items):
            self.table.insertRow(row)

            if isinstance(item, dict):
                title = item.get("title") or "Sem título"
                platform = item.get("platform", "Geral")
                status = item.get("status", "Concluído")
                file_path = item.get("file_path", "")
            else:
                title = getattr(item, "title", "Sem título") or "Sem título"
                platform = getattr(item, "platform", "Geral")
                status = getattr(item, "status", "Concluído")
                file_path = getattr(item, "file_path", "")

            title_item = QTableWidgetItem(title)
            title_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 0, title_item)

            plat_item = QTableWidgetItem(str(platform).capitalize())
            plat_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 1, plat_item)

            status_item = QTableWidgetItem(status)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 2, status_item)

            # Container para botões de ação
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(6)
            actions_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            btn_open = QPushButton("▶ Abrir")
            btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_open.setStyleSheet(f"""
                QPushButton {{
                    background-color: {ThemeColors.PRIMARY};
                    color: #FFFFFF;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 10px;
                    font-weight: bold;
                }}
            """)
            btn_open.clicked.connect(lambda _, p=file_path: self._open_file(p))

            btn_folder = QPushButton("📁 Pasta")
            btn_folder.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_folder.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: 1px solid {ThemeColors.BORDER};
                    color: {ThemeColors.TEXT};
                    border-radius: 4px;
                    padding: 4px 10px;
                }}
                QPushButton:hover {{
                    border-color: {ThemeColors.PRIMARY};
                }}
            """)
            btn_folder.clicked.connect(lambda _, p=file_path: self._open_folder(p))

            actions_layout.addWidget(btn_open)
            actions_layout.addWidget(btn_folder)

            self.table.setCellWidget(row, 3, actions_widget)

    def _open_file(self, file_path: str) -> None:
        """Abre a mídia no player padrão do sistema operacional."""
        if not file_path:
            QMessageBox.warning(self, "Aviso", "Caminho do arquivo não especificado.")
            return

        path = Path(file_path)
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))
        else:
            QMessageBox.warning(self, "Aviso", f"O arquivo não foi localizado em:\n{file_path}")

    def _open_folder(self, file_path: str) -> None:
        """Abre o Explorer selecionando diretamente o arquivo baixado."""
        if not file_path:
            QMessageBox.warning(self, "Aviso", "Caminho do arquivo não especificado.")
            return

        path = Path(file_path)
        if path.exists():
            if sys.platform == "win32":
                subprocess.Popen(f'explorer /select,"{path.resolve()}"')
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent.resolve())))
        else:
            QMessageBox.warning(self, "Aviso", f"A pasta ou o arquivo não existe em:\n{file_path}")