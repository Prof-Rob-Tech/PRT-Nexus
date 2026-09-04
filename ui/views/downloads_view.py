"""
===========================================================
PRT Nexus - Downloads View (Exibição do Título do Vídeo)
Class: DownloadsView
Description: Gerenciador de downloads assíncrono com extração do título do vídeo.
===========================================================
"""

import os
import shutil
from PySide6.QtCore import Qt, Signal, Slot, QThread
from PySide6.QtWidgets import (
    QComboBox,
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

from theme.colors import ThemeColors

YTDLP_AVAILABLE = False
try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False

IMAGEIO_FFMPEG_AVAILABLE = False
try:
    import imageio_ffmpeg
    IMAGEIO_FFMPEG_AVAILABLE = True
except ImportError:
    IMAGEIO_FFMPEG_AVAILABLE = False


def get_ffmpeg_path() -> str | None:
    """Retorna o caminho do executável do FFmpeg se disponível."""
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    if IMAGEIO_FFMPEG_AVAILABLE:
        try:
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            return None
    return None


class DownloadWorker(QThread):
    """Worker rodando em segundo plano para efetuar o download sem travar a UI."""

    title_signal = Signal(str)               # título do vídeo extraído
    progress_signal = Signal(int, str, str)   # percentual, tamanho, status
    finished_signal = Signal(bool, str, str)  # sucesso, tamanho_final, mensagem

    def __init__(self, url: str, quality: str, save_dir: str = "downloads") -> None:
        super().__init__()
        self.url = url
        self.quality = quality
        self.save_dir = save_dir
        self.last_size_str = "Calculando..."
        self._title_emitted = False
        os.makedirs(self.save_dir, exist_ok=True)

    def run(self) -> None:
        if not YTDLP_AVAILABLE:
            self.finished_signal.emit(False, "--", "yt-dlp não está instalado no ambiente Python.")
            return

        def _progress_hook(d: dict) -> None:
            # Tenta capturar o título do vídeo assim que os metadados forem carregados
            info = d.get("info_dict", {})
            title = info.get("title")
            if title and not self._title_emitted:
                self._title_emitted = True
                self.title_signal.emit(title)

            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes", 0)
                percent = int(downloaded / total * 100) if total > 0 else 0

                size_mb = total / (1024 * 1024) if total > 0 else (downloaded / (1024 * 1024))
                if size_mb > 0:
                    self.last_size_str = f"{size_mb:.1f} MB"

                speed = d.get("speed", 0) or 0
                speed_mb = speed / (1024 * 1024)
                status_str = f"Baixando ({speed_mb:.1f} MB/s)" if speed_mb > 0 else "Baixando..."

                self.progress_signal.emit(percent, self.last_size_str, status_str)

            elif d.get("status") == "finished":
                filename = d.get("filename")
                if filename and os.path.exists(filename):
                    size_mb = os.path.getsize(filename) / (1024 * 1024)
                    self.last_size_str = f"{size_mb:.1f} MB"
                self.progress_signal.emit(100, self.last_size_str, "Processando...")

        ffmpeg_bin = get_ffmpeg_path()

        ydl_opts = {
            "outtmpl": os.path.join(self.save_dir, "%(title)s.%(ext)s"),
            "progress_hooks": [_progress_hook],
            "quiet": True,
            "no_warnings": True,
            "nocheckcertificate": True,
            "noplaylist": True,
        }

        if ffmpeg_bin:
            ydl_opts["ffmpeg_location"] = ffmpeg_bin

        if "Áudio" in self.quality:
            ydl_opts["format"] = "bestaudio/best"
        elif ffmpeg_bin:
            if "1080p" in self.quality:
                ydl_opts["format"] = "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
            elif "720p" in self.quality:
                ydl_opts["format"] = "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
            elif "480p" in self.quality:
                ydl_opts["format"] = "bestvideo[height<=480]+bestaudio/best[height<=480]/best"
            else:
                ydl_opts["format"] = "bestvideo+bestaudio/best"
        else:
            ydl_opts["format"] = "best"

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=True)
                if info:
                    title = info.get("title")
                    if title and not self._title_emitted:
                        self._title_emitted = True
                        self.title_signal.emit(title)

                    filename = ydl.prepare_filename(info)
                    if os.path.exists(filename):
                        size_mb = os.path.getsize(filename) / (1024 * 1024)
                        self.last_size_str = f"{size_mb:.1f} MB"
                    elif "requested_downloads" in info:
                        for req in info["requested_downloads"]:
                            fpath = req.get("filepath")
                            if fpath and os.path.exists(fpath):
                                size_mb = os.path.getsize(fpath) / (1024 * 1024)
                                self.last_size_str = f"{size_mb:.1f} MB"
                                break

            self.finished_signal.emit(True, self.last_size_str, "Concluído ✅")
        except Exception as err:
            self.finished_signal.emit(False, self.last_size_str, str(err))


class DownloadsView(QWidget):
    """View responsável pelo gerenciamento de downloads."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.active_workers: list[DownloadWorker] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)

        lbl_title = QLabel("Gerenciador de Downloads")
        lbl_title.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {ThemeColors.TEXT};")
        main_layout.addWidget(lbl_title)

        input_card = QWidget()
        input_card.setStyleSheet(f"background-color: {ThemeColors.CARD}; border-radius: 8px;")
        input_layout = QHBoxLayout(input_card)
        input_layout.setContentsMargins(12, 12, 12, 12)
        input_layout.setSpacing(10)

        self.txt_url = QLineEdit()
        self.txt_url.setPlaceholderText("Cole o link aqui (YouTube, TikTok, Kiwify, Drive, etc...)...")
        self.txt_url.setStyleSheet(f"""
            QLineEdit {{
                background-color: {ThemeColors.BACKGROUND};
                color: {ThemeColors.TEXT};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
                padding: 10px 14px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {ThemeColors.PRIMARY};
            }}
        """)
        self.txt_url.returnPressed.connect(self._on_click_download)

        self.combo_quality = QComboBox()
        self.combo_quality.addItems(["Melhor Qualidade", "1080p", "720p", "480p", "Apenas Áudio (MP3)"])
        self.combo_quality.setFixedWidth(160)
        self.combo_quality.setStyleSheet(f"""
            QComboBox {{
                background-color: {ThemeColors.BACKGROUND};
                color: {ThemeColors.TEXT};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
            }}
        """)

        self.btn_download = QPushButton("⚡ Baixar")
        self.btn_download.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_download.setStyleSheet(f"""
            QPushButton {{
                background-color: {ThemeColors.PRIMARY};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """)
        self.btn_download.clicked.connect(self._on_click_download)

        input_layout.addWidget(self.txt_url, stretch=1)
        input_layout.addWidget(self.combo_quality)
        input_layout.addWidget(self.btn_download)

        main_layout.addWidget(input_card)

        # Tabela
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Item / Título", "Progresso", "Tamanho", "Status", "Ações"])
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {ThemeColors.CARD};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
                gridline-color: {ThemeColors.BORDER};
                color: {ThemeColors.TEXT};
            }}
            QHeaderView::section {{
                background-color: {ThemeColors.BACKGROUND};
                color: {ThemeColors.TEXT_SECONDARY};
                padding: 10px;
                font-weight: bold;
                border: none;
                border-bottom: 1px solid {ThemeColors.BORDER};
            }}
            QTableWidget::item {{
                padding: 8px;
            }}
        """)

        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)

        self.table.setColumnWidth(1, 180)
        self.table.setColumnWidth(2, 110)
        self.table.setColumnWidth(3, 150)
        self.table.setColumnWidth(4, 70)

        main_layout.addWidget(self.table, stretch=1)

    def add_download_url(self, url: str) -> None:
        self.txt_url.clear()
        self.txt_url.clearFocus()
        self._start_download(url, self.combo_quality.currentText())

    def _on_click_download(self) -> None:
        url = self.txt_url.text().strip()
        if not url:
            return
        self.txt_url.clear()
        self.txt_url.clearFocus()
        self._start_download(url, self.combo_quality.currentText())

    def _remove_table_row_by_widget(self, widget: QWidget) -> None:
        for r in range(self.table.rowCount()):
            if self.table.cellWidget(r, 4) == widget:
                self.table.removeRow(r)
                break

    def _start_download(self, url: str, quality: str, save_dir: str | None = None) -> None:
        if not YTDLP_AVAILABLE:
            QMessageBox.critical(
                self,
                "Biblioteca Ausente",
                "A biblioteca 'yt-dlp' não está instalada.\nExecute: pip install yt-dlp"
            )
            return

        if save_dir is None:
            save_dir = os.path.join(os.path.expanduser("~"), "Downloads", "PRT_Nexus")

        row = self.table.rowCount()
        self.table.insertRow(row)

        item_title = QTableWidgetItem("Obtendo título...")
        item_title.setToolTip(url)
        item_title.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.table.setItem(row, 0, item_title)

        progress_bar = QProgressBar()
        progress_bar.setValue(0)
        progress_bar.setFixedHeight(20)
        progress_bar.setTextVisible(True)
        progress_bar.setFormat("%p%")
        progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {ThemeColors.BACKGROUND};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 4px;
                text-align: center;
                color: #FFFFFF;
                font-size: 11px;
                font-weight: bold;
            }}
            QProgressBar::chunk {{
                background-color: {ThemeColors.PRIMARY};
                border-radius: 3px;
            }}
        """)
        self.table.setCellWidget(row, 1, progress_bar)

        item_size = QTableWidgetItem("Calculando...")
        item_size.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 2, item_size)

        item_status = QTableWidgetItem("Conectando... ⏳")
        item_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 3, item_status)

        btn_remove = QPushButton("🗑️")
        btn_remove.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_remove.setStyleSheet("background: transparent; border: none; font-size: 13px;")
        btn_remove.clicked.connect(lambda _, b=btn_remove: self._remove_table_row_by_widget(b))
        self.table.setCellWidget(row, 4, btn_remove)

        worker = DownloadWorker(url, quality, save_dir=save_dir)

        def update_title(title: str) -> None:
            item_title.setText(title)

        def update_progress(percent: int, size_str: str, status_str: str) -> None:
            progress_bar.setValue(percent)
            item_size.setText(size_str)
            item_status.setText(status_str)

        def update_finished(success: bool, final_size_str: str, message: str) -> None:
            item_size.setText(final_size_str)
            if success:
                progress_bar.setValue(100)
                item_status.setText("Concluído ✅")
            else:
                item_status.setText("Erro ❌")
                item_status.setToolTip(message)

            if worker in self.active_workers:
                self.active_workers.remove(worker)

        worker.title_signal.connect(update_title)
        worker.progress_signal.connect(update_progress)
        worker.finished_signal.connect(update_finished)

        self.active_workers.append(worker)
        worker.start()

    @Slot(str, str)
    def add_url_to_queue(self, url: str, subfolder: str = "Kiwify/DIA 01") -> None:
        """Adiciona um URL à fila criando a pasta correspondente e iniciando o download assíncrono."""
        target_path = os.path.join(os.path.expanduser("~"), "Downloads", "PRT_Nexus", subfolder)
        os.makedirs(target_path, exist_ok=True)
        self._start_download(url, self.combo_quality.currentText(), save_dir=target_path)