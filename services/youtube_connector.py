"""
===========================================================
PRT Nexus - YouTube Connector Backend
Class: YouTubeConnector, YouTubeWorker
Description: Gerenciamento de extração de metadados, controle
             de pausa/cancelamento e download via yt-dlp.
===========================================================
"""

import os
import time
from typing import Optional
import yt_dlp
from PySide6.QtCore import QObject, QThread, Signal

try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except ImportError:
    pass


class YouTubeWorker(QThread):
    """Thread dedicada com suporte a pausa e cancelamento de downloads."""

    progress_signal = Signal(dict)
    item_finished_signal = Signal(str)
    finished_signal = Signal(str, str)
    error_signal = Signal(str)

    def __init__(self, url: str, ydl_opts: dict, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.url = url
        self.ydl_opts = ydl_opts
        self._is_paused = False
        self._is_cancelled = False
        self._last_update_time = 0.0

    def pause_download(self) -> None:
        """Pausa a execução do download."""
        self._is_paused = True

    def resume_download(self) -> None:
        """Retoma a execução do download."""
        self._is_paused = False

    def stop_download(self) -> None:
        """Solicita o cancelamento imediato do download."""
        self._is_cancelled = True
        self._is_paused = False

    def _progress_hook(self, data: dict) -> None:
        if self._is_cancelled:
            raise Exception("Download interrompido pelo usuário.")

        while self._is_paused:
            if self._is_cancelled:
                raise Exception("Download interrompido pelo usuário.")
            self.msleep(200)

        status = data.get("status")
        if status == "downloading":
            now = time.time()
            if now - self._last_update_time < 0.1:
                return
            self._last_update_time = now

            downloaded = data.get("downloaded_bytes", 0)
            total = data.get("total_bytes") or data.get("total_bytes_estimate", 1)
            percent = (downloaded / total) * 100 if total > 0 else 0

            # Tratamento da velocidade para evitar 'Unknown'
            raw_speed = data.get("speed")
            speed_str = data.get("_speed_str")
            if raw_speed is not None and raw_speed > 0:
                if raw_speed >= 1048576:
                    formatted_speed = f"{raw_speed / 1048576:.2f} MB/s"
                elif raw_speed >= 1024:
                    formatted_speed = f"{raw_speed / 1024:.1f} KB/s"
                else:
                    formatted_speed = f"{int(raw_speed)} B/s"
            elif speed_str and "unknown" not in str(speed_str).lower():
                formatted_speed = str(speed_str).strip()
            else:
                formatted_speed = "calculando..."

            self.progress_signal.emit({
                "percent": percent,
                "speed": formatted_speed,
                "eta": data.get("_eta_str", "00:00").strip(),
                "downloaded": data.get("_downloaded_bytes_str", "0 B").strip(),
                "total": data.get("_total_bytes_str", "0 B").strip(),
                "filename": os.path.basename(data.get("filename", "")),
            })

    def _postprocessor_hook(self, data: dict) -> None:
        if self._is_cancelled:
            raise Exception("Download interrompido pelo usuário.")

        if data.get("status") == "finished":
            info = data.get("info_dict", {})
            filepath = info.get("_filename") or data.get("filename")
            if filepath and os.path.exists(filepath):
                self.item_finished_signal.emit(filepath)

    def run(self) -> None:
        try:
            opts = self.ydl_opts.copy()
            opts["progress_hooks"] = [self._progress_hook]
            opts["postprocessor_hooks"] = [self._postprocessor_hook]

            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.url, download=True)
                filename = ydl.prepare_filename(info) if info else ""

            if not self._is_cancelled:
                self.finished_signal.emit("Download concluído com sucesso!", filename)
        except Exception as err:
            self.error_signal.emit(str(err))


class YouTubeConnector:
    """Interface principal do backend para o conector do YouTube."""

    @staticmethod
    def download_video(
        url: str,
        output_path: str,
        quality_mode: str = "max",
        is_playlist: bool = False,
        username: str = "",
        password: str = "",
        custom_content: str = "",
        custom_mod: str = "",
        custom_item: str = ""
    ) -> YouTubeWorker:

        sub_paths = []
        if custom_content:
            sub_paths.append(custom_content)
        elif is_playlist:
            sub_paths.append("%(uploader,playlist_title)s")

        if custom_mod:
            sub_paths.append(custom_mod)

        filename_fmt = "%(title)s.%(ext)s"
        if is_playlist and not custom_item:
            filename_fmt = "%(playlist_index)s - %(title)s.%(ext)s"
        elif custom_item:
            filename_fmt = f"{custom_item} - %(title)s.%(ext)s"

        out_pattern = os.path.join(output_path, *sub_paths, filename_fmt)

        ydl_opts = {
            "outtmpl": out_pattern,
            "noplaylist": not is_playlist,
            "no_color": True,
            "ignoreerrors": True,
            "postprocessor_args": {
                "Merger": ["-c:a", "aac"]
            }
        }

        if username and password:
            ydl_opts["username"] = username
            ydl_opts["password"] = password

        if quality_mode == "audio":
            ydl_opts["format"] = "ba/b"
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
        elif quality_mode == "1080p":
            ydl_opts["format"] = "bv*[height<=1080]+ba[ext=m4a]/bv*[height<=1080]+ba/b"
            ydl_opts["merge_output_format"] = "mp4"
        elif quality_mode == "720p":
            ydl_opts["format"] = "bv*[height<=720]+ba[ext=m4a]/bv*[height<=720]+ba/b"
            ydl_opts["merge_output_format"] = "mp4"
        else:
            ydl_opts["format"] = "bv*+ba[ext=m4a]/bv*+ba/b"
            ydl_opts["merge_output_format"] = "mp4"

        return YouTubeWorker(url, ydl_opts)