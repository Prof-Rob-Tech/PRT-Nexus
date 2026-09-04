"""
===========================================================
PRT Nexus - Download Worker
Class: DownloadWorker
Description: Thread assíncrona para downloads de mídia via yt-dlp.
===========================================================
"""

from pathlib import Path
import re
from PySide6.QtCore import QObject, Signal
import yt_dlp


class DownloadWorker(QObject):
    """Executa o download via yt-dlp emitindo sinais de progresso e status."""

    progress_updated = Signal(str, float, str, str)  # (task_id, percent, speed, size)
    finished = Signal(str, dict)                    # (task_id, info_dict)
    error = Signal(str, str)                        # (task_id, error_msg)

    def __init__(
        self,
        task_id: str,
        url: str,
        quality: str,
        output_dir: str | Path = "downloads_files",
    ) -> None:
        super().__init__()
        self.task_id = task_id
        self.url = url
        self.quality = quality
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        """Inicia a extração e download restringindo a playlists."""
        format_spec = "bv*+ba/b"
        if "1080p" in self.quality:
            format_spec = "bv*[height<=1080]+ba/b[height<=1080]/b"
        elif "720p" in self.quality:
            format_spec = "bv*[height<=720]+ba/b[height<=720]/b"
        elif "Áudio" in self.quality:
            format_spec = "ba/b"

        ydl_opts = {
            "format": format_spec,
            "outtmpl": str(self.output_dir / "%(title)s.%(ext)s"),
            "progress_hooks": [self._progress_hook],
            "noplaylist": True,
            "nocolor": True,
            "quiet": True,
            "no_warnings": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=True)
                if not self._is_cancelled:
                    self.finished.emit(self.task_id, info or {})
        except Exception as e:
            self.error.emit(self.task_id, str(e))

    def _progress_hook(self, d: dict) -> None:
        if self._is_cancelled:
            raise Exception("Download cancelado pelo usuário.")

        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
            downloaded = d.get("downloaded_bytes", 0)
            percent = (downloaded / total) * 100
            
            speed_raw = d.get("_speed_str", "N/A")
            # Remove códigos ANSI de cor enviadas pelo terminal
            speed = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", speed_raw).strip()

            size_mb = f"{total / (1024 * 1024):.1f} MB"
            self.progress_updated.emit(self.task_id, percent, speed, size_mb)