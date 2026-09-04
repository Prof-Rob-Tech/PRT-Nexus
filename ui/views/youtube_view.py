"""
===========================================================
PRT Nexus - YouTube View
Class: YouTubeView
Description: Interface completa do Conector do YouTube.
===========================================================
"""

import os
import re
from PySide6.QtCore import QByteArray, QSize, Qt, QThread, Signal
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.extractors.youtube_connector import YouTubeConnector
from theme.colors import ThemeColors

YOUTUBE_SVG = '<svg viewBox="0 0 24 24"><path fill="#FF0000" d="M23.5 6.2a3 3 0 0 0-2.1-2.1C19.5 3.5 12 3.5 12 3.5s-7.5 0-9.4.5A3 3 0 0 0 .5 6.2 31.8 31.8 0 0 0 0 12c0 1.9.2 3.8.5 5.8a3 3 0 0 0 2.1 2.1c1.9.5 9.4.5 9.4.5s7.5 0 9.4-.5a3 3 0 0 0 2.1-2.1c.3-2 .5-3.9.5-5.8s-.2-3.8-.5-5.8z"/><polygon fill="#FFFFFF" points="9.6,15.6 15.8,12 9.6,8.4"/></svg>'


def make_yt_pixmap(size: int = 32) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(YOUTUBE_SVG.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


class YouTubeView(QWidget):
    """View do Conector do YouTube no estilo completo do PRT Nexus."""

    def __init__(self) -> None:
        super().__init__()
        self.download_worker = None
        self.default_dest = os.path.expanduser("~/Downloads/PRT_Nexus")
        self.added_files = set()
        self.is_paused = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        style_card_title = "font-size: 15px; font-weight: bold; color: #FACC15;"

        header_title_layout = QHBoxLayout()
        header_title_layout.setSpacing(10)
        header_title_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        lbl_icon = QLabel()
        lbl_icon.setPixmap(make_yt_pixmap(34))

        lbl_header_title = QLabel("Conector Youtube")
        lbl_header_title.setStyleSheet("font-size: 24px; font-weight: bold; color: #FACC15;")

        header_title_layout.addWidget(lbl_icon)
        header_title_layout.addWidget(lbl_header_title)

        lbl_header_sub = QLabel("Capture, extraia e gerencie conteúdos diretamente do Youtube.")
        lbl_header_sub.setStyleSheet(f"font-size: 12px; color: {ThemeColors.TEXT_SECONDARY};")

        main_layout.addLayout(header_title_layout)
        main_layout.addWidget(lbl_header_sub)

        card_capture = self._create_card()
        layout_capture = QVBoxLayout(card_capture)
        layout_capture.setSpacing(10)

        lbl_cap_title = QLabel("🔗 Captura de Mídia - Youtube")
        lbl_cap_title.setStyleSheet(style_card_title)

        self.txt_url = QLineEdit()
        self.txt_url.setPlaceholderText("Cole o link do vídeo, playlist ou canal aqui...")
        self._apply_input_style(self.txt_url)

        row_cap_opts = QHBoxLayout()
        row_cap_opts.setSpacing(10)

        lbl_qual = QLabel("Qualidade:")
        lbl_qual.setStyleSheet("color: #FACC15; font-weight: bold; font-size: 13px;")

        self.cmb_quality = QComboBox()
        self.cmb_quality.addItems([
            "Vídeo - Max Qualidade (MP4)",
            "Vídeo - 1080p (MP4)",
            "Vídeo - 720p (MP4)",
            "Áudio - MP3 (Alta Qualidade)"
        ])
        self._apply_combo_style(self.cmb_quality)

        self.btn_download_single = QPushButton("⬇ Baixar Mídia Avulsa")
        self.btn_download_single.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_download_single.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1D4ED8; }
        """)
        self.btn_download_single.clicked.connect(lambda: self._on_start_download(is_playlist=False))

        self.btn_map_playlist = QPushButton("📖 Mapear e Baixar Playlist / Canal")
        self.btn_map_playlist.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_map_playlist.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #047857; }
        """)
        self.btn_map_playlist.clicked.connect(lambda: self._on_start_download(is_playlist=True))

        row_cap_opts.addWidget(lbl_qual)
        row_cap_opts.addWidget(self.cmb_quality, stretch=1)
        row_cap_opts.addWidget(self.btn_download_single)
        row_cap_opts.addWidget(self.btn_map_playlist)

        layout_capture.addWidget(lbl_cap_title)
        layout_capture.addWidget(self.txt_url)
        layout_capture.addLayout(row_cap_opts)
        main_layout.addWidget(card_capture)

        row_middle = QHBoxLayout()
        row_middle.setSpacing(16)

        col_left = QVBoxLayout()
        col_left.setSpacing(16)

        card_auth = self._create_card()
        layout_auth = QVBoxLayout(card_auth)
        lbl_auth_title = QLabel("🔑 Autenticação (Áreas Pagas / Privadas)")
        lbl_auth_title.setStyleSheet(style_card_title)

        self.txt_user = QLineEdit()
        self.txt_user.setPlaceholderText("E-mail / Usuário")
        self._apply_input_style(self.txt_user)

        self.txt_pass = QLineEdit()
        self.txt_pass.setPlaceholderText("Senha")
        self.txt_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self._apply_input_style(self.txt_pass)

        layout_auth.addWidget(lbl_auth_title)
        layout_auth.addWidget(self.txt_user)
        layout_auth.addWidget(self.txt_pass)

        card_dest = self._create_card()
        layout_dest = QVBoxLayout(card_dest)
        lbl_dest_title = QLabel("📁 Pasta de Destino")
        lbl_dest_title.setStyleSheet(style_card_title)

        row_dest_path = QHBoxLayout()
        self.txt_dest_path = QLineEdit(self.default_dest)
        self._apply_input_style(self.txt_dest_path)

        btn_browse = QPushButton("Alterar")
        btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_browse.setStyleSheet(f"""
            QPushButton {{
                background-color: {ThemeColors.BACKGROUND};
                color: {ThemeColors.TEXT};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
                padding: 6px 12px;
            }}
        """)
        btn_browse.clicked.connect(self._on_select_folder)

        row_dest_path.addWidget(self.txt_dest_path, stretch=1)
        row_dest_path.addWidget(btn_browse)

        layout_dest.addWidget(lbl_dest_title)
        layout_dest.addLayout(row_dest_path)

        col_left.addWidget(card_auth)
        col_left.addWidget(card_dest)

        card_org = self._create_card()
        layout_org = QVBoxLayout(card_org)
        lbl_org_title = QLabel("🗂 Organização de Pastas (Playlist / Canal)")
        lbl_org_title.setStyleSheet(style_card_title)

        self.txt_content_name = QLineEdit()
        self.txt_content_name.setPlaceholderText("Nome do Conteúdo / Playlist / Canal")
        self._apply_input_style(self.txt_content_name)

        row_mod = QHBoxLayout()
        cmb_mod = QComboBox()
        cmb_mod.addItem("Mod 1")
        self._apply_combo_style(cmb_mod)
        self.txt_mod_name = QLineEdit()
        self.txt_mod_name.setPlaceholderText("Nome do Módulo / Seção")
        self._apply_input_style(self.txt_mod_name)
        row_mod.addWidget(cmb_mod)
        row_mod.addWidget(self.txt_mod_name, stretch=1)

        row_item = QHBoxLayout()
        cmb_item = QComboBox()
        cmb_item.addItem("Item 1")
        self._apply_combo_style(cmb_item)
        self.txt_item_name = QLineEdit()
        self.txt_item_name.setPlaceholderText("Nome do Vídeo")
        self._apply_input_style(self.txt_item_name)
        row_item.addWidget(cmb_item)
        row_item.addWidget(self.txt_item_name, stretch=1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {ThemeColors.BACKGROUND};
                border-radius: 4px;
                border: none;
            }}
            QProgressBar::chunk {{
                background-color: #3B82F6;
                border-radius: 4px;
            }}
        """)

        row_controls = QHBoxLayout()
        self.lbl_status = QLabel("Aguardando link de download...")
        self.lbl_status.setFixedHeight(24)
        self.lbl_status.setStyleSheet(f"color: {ThemeColors.TEXT_SECONDARY}; font-size: 12px;")

        self.btn_pause = QPushButton("⏸  Pausar")
        self.btn_pause.setEnabled(False)
        self.btn_pause.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pause.setStyleSheet("""
            QPushButton {
                background-color: #D97706;
                color: #FFFFFF;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
                min-width: 85px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #B45309; }
            QPushButton:disabled { background-color: #4B5563; color: #9CA3AF; }
        """)
        self.btn_pause.clicked.connect(self._on_toggle_pause)

        self.btn_stop = QPushButton("⏹ Parar")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background-color: #DC2626;
                color: #FFFFFF;
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #B91C1C; }
            QPushButton:disabled { background-color: #4B5563; color: #9CA3AF; }
        """)
        self.btn_stop.clicked.connect(self._on_stop_download)

        row_controls.addWidget(self.lbl_status, stretch=1)
        row_controls.addWidget(self.btn_pause)
        row_controls.addWidget(self.btn_stop)

        layout_org.addWidget(lbl_org_title)
        layout_org.addWidget(self.txt_content_name)
        layout_org.addLayout(row_mod)
        layout_org.addLayout(row_item)
        layout_org.addWidget(self.progress_bar)
        layout_org.addLayout(row_controls)

        row_middle.addLayout(col_left, stretch=1)
        row_middle.addWidget(card_org, stretch=1)
        main_layout.addLayout(row_middle)

        card_table = self._create_card()
        layout_table = QVBoxLayout(card_table)

        lbl_tbl_title = QLabel("📦 Mídias Concluídas do Youtube")
        lbl_tbl_title.setStyleSheet(style_card_title)

        self.table_downloads = QTableWidget(0, 4)
        headers = ["#", "Título / Nome do Arquivo", "Caminho Salvo", "Status"]

        for col, text in enumerate(headers):
            item = QTableWidgetItem(text)
            if col in (0, 3):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self.table_downloads.setHorizontalHeaderItem(col, item)

        header = self.table_downloads.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table_downloads.setColumnWidth(0, 60)

        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table_downloads.setColumnWidth(3, 140)

        self.table_downloads.verticalHeader().setVisible(False)
        self.table_downloads.setStyleSheet(f"""
            QTableWidget {{
                background-color: transparent;
                color: {ThemeColors.TEXT};
                border: 1px solid {ThemeColors.BORDER};
                gridline-color: {ThemeColors.BORDER};
            }}
            QHeaderView::section {{
                background-color: {ThemeColors.BACKGROUND};
                color: {ThemeColors.TEXT_SECONDARY};
                padding: 6px;
                border: none;
                font-weight: bold;
            }}
        """)

        layout_table.addWidget(lbl_tbl_title)
        layout_table.addWidget(self.table_downloads)
        main_layout.addWidget(card_table, stretch=1)

    def _create_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {ThemeColors.CARD};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
            }}
        """)
        return card

    def _apply_input_style(self, widget: QLineEdit) -> None:
        widget.setStyleSheet(f"""
            QLineEdit {{
                background-color: {ThemeColors.BACKGROUND};
                color: {ThemeColors.TEXT};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }}
        """)

    def _apply_combo_style(self, widget: QComboBox) -> None:
        widget.setStyleSheet(f"""
            QComboBox {{
                background-color: {ThemeColors.BACKGROUND};
                color: {ThemeColors.TEXT};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
                padding: 6px 10px;
            }}
        """)

    def _on_select_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Selecione a pasta de destino", self.txt_dest_path.text())
        if path:
            self.txt_dest_path.setText(path)

    def _add_file_to_table(self, filepath: str) -> None:
        if not filepath:
            return

        if re.search(r'\.f\d+.*?\.(mp4|m4a|webm|mkv)$', filepath):
            return

        if filepath in self.added_files:
            return
        self.added_files.add(filepath)

        row = self.table_downloads.rowCount()
        self.table_downloads.insertRow(row)

        item_id = QTableWidgetItem(str(row + 1))
        item_id.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        item_title = QTableWidgetItem(os.path.basename(filepath))
        item_path = QTableWidgetItem(filepath)

        item_status = QTableWidgetItem("Concluído")
        item_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        self.table_downloads.setItem(row, 0, item_id)
        self.table_downloads.setItem(row, 1, item_title)
        self.table_downloads.setItem(row, 2, item_path)
        self.table_downloads.setItem(row, 3, item_status)

    def _on_start_download(self, is_playlist: bool = False) -> None:
        url = self.txt_url.text().strip()
        if not url:
            QMessageBox.warning(self, "Aviso", "Por favor, informe a URL do vídeo ou canal do YouTube.")
            return

        dest_folder = self.txt_dest_path.text().strip() or self.default_dest
        os.makedirs(dest_folder, exist_ok=True)

        idx = self.cmb_quality.currentIndex()
        quality_mode = "max"
        if idx == 1:
            quality_mode = "1080p"
        elif idx == 2:
            quality_mode = "720p"
        elif idx == 3:
            quality_mode = "audio"

        self.btn_download_single.setEnabled(False)
        self.btn_map_playlist.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_stop.setEnabled(True)
        self.is_paused = False
        self.btn_pause.setText("⏸ Pausar")
        self.lbl_status.setText("Iniciando download da playlist/canal..." if is_playlist else "Iniciando download...")

        self.download_worker = YouTubeConnector.download_video(
            url=url,
            output_path=dest_folder,
            quality_mode=quality_mode,
            is_playlist=is_playlist,
            username=self.txt_user.text().strip(),
            password=self.txt_pass.text().strip(),
            custom_content=self.txt_content_name.text().strip(),
            custom_mod=self.txt_mod_name.text().strip(),
            custom_item=self.txt_item_name.text().strip()
        )
        self.download_worker.progress_signal.connect(self._on_progress)
        self.download_worker.item_finished_signal.connect(self._add_file_to_table)
        self.download_worker.finished_signal.connect(self._on_download_finished)
        self.download_worker.error_signal.connect(self._on_download_error)
        self.download_worker.start()

    def _on_toggle_pause(self) -> None:
        if not self.download_worker:
            return

        if self.is_paused:
            self.download_worker.resume_download()
            self.is_paused = False
            self.btn_pause.setText("⏸  Pausar")
            self.lbl_status.setText("Retomando download...")
        else:
            self.download_worker.pause_download()
            self.is_paused = True
            self.btn_pause.setText("▶  Retomar")
            self.lbl_status.setText("Download pausado.")

    def _on_stop_download(self) -> None:
        if self.download_worker:
            self.lbl_status.setText("Cancelando download...")
            self.download_worker.stop_download()

    def _reset_download_buttons(self) -> None:
        self.btn_download_single.setEnabled(True)
        self.btn_map_playlist.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.btn_pause.setText("⏸  Pausar")
        self.is_paused = False

    def _on_progress(self, data: dict) -> None:
        if self.is_paused:
            return
        percent = int(data.get("percent", 0))
        self.progress_bar.setValue(percent)
        filename = data.get("filename", "")
        
        # Corta nomes de arquivos muito longos para evitar reajuste de layout
        if len(filename) > 32:
            filename = filename[:29] + "..."
            
        self.lbl_status.setText(
            f"Baixando: {filename} ({percent}%) | Vel: {data.get('speed')}"
        )

    def _on_download_finished(self, msg: str, filepath: str) -> None:
        self._reset_download_buttons()
        self.progress_bar.setValue(100)
        self.lbl_status.setText("Processo de download concluído!")
        if filepath:
            self._add_file_to_table(filepath)

    def _on_download_error(self, err: str) -> None:
        self._reset_download_buttons()
        if "interrompido pelo usuário" in err.lower():
            self.lbl_status.setText("Download cancelado pelo usuário.")
        else:
            self.lbl_status.setText(f"Erro no download: {err}")
            QMessageBox.critical(self, "Erro", f"Falha no download:\n{err}")