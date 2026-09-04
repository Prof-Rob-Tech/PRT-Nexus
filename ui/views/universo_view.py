"""
===========================================================
PRT Nexus - Universo Técnico View
Description: Conector com automação Chromium (Playwright), 
             pastas numeradas por sequência de módulos,
             centralização de tabela e barra de status ampliada.
===========================================================
"""

import os
import re
import requests
from bs4 import BeautifulSoup
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFormLayout, QComboBox, QFrame, QGridLayout,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog
)

import yt_dlp
from theme.colors import ThemeColors

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


def sanitize_filename(name: str) -> str:
    """Remove caracteres inválidos para nomes de arquivos e pastas no Windows/Linux."""
    clean = re.sub(r'[\\/*?:"<>|]', '_', name)
    return clean.strip()


def strip_ansi(text: str) -> str:
    """Remove códigos de escape ANSI/cor do texto."""
    return re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)


class DownloadWorker(QThread):
    """Thread com automação Chromium, interceptor de rede e salvamento numerado por módulo."""
    progress_signal = Signal(float, str)
    item_completed_signal = Signal(str, str, str)  # (Título/Aula, Caminho Salvo, Status)
    finished_signal = Signal(bool, str)

    def __init__(self, url: str, output_path: str, is_audio_only: bool = False, username: str = "", password: str = "", is_mapping: bool = False):
        super().__init__()
        self.url = url
        self.output_path = output_path
        self.is_audio_only = is_audio_only
        self.username = username
        self.password = password
        self.is_mapping = is_mapping

    def _perform_inpage_login(self, page) -> None:
        """Efetua o login na plataforma."""
        self.progress_signal.emit(5.0, "Acessando página do curso...")
        page.goto(self.url, timeout=45000)
        page.wait_for_timeout(3000)

        if not (self.username and self.password):
            return

        try:
            user_field = page.locator('#username, input[name="username"], #user_login, input[name="log"]').first
            
            if not user_field.is_visible(timeout=2000):
                entrar_btn = page.locator('a:has-text("Entrar"), button:has-text("Entrar"), a:has-text("Minha conta")').first
                if entrar_btn.is_visible(timeout=2000):
                    self.progress_signal.emit(10.0, "Abrindo formulário de login...")
                    entrar_btn.click()
                    page.wait_for_timeout(2500)

            user_field = page.locator('#username, input[name="username"], #user_login, input[name="log"]').first
            pass_field = page.locator('#password, input[name="password"], #user_pass, input[name="pwd"]').first
            login_btn = page.locator('button[name="login"], input[name="login"], button:has-text("Entrar"), input[value="Entrar"], #wp-submit').first

            if user_field.is_visible(timeout=3000):
                self.progress_signal.emit(15.0, "Preenchendo credenciais e realizando login...")
                user_field.fill(self.username)
                pass_field.fill(self.password)
                page.wait_for_timeout(500)
                
                if login_btn.is_visible():
                    login_btn.click()
                    page.wait_for_timeout(4000)

            if page.url != self.url:
                page.goto(self.url, timeout=45000)
                page.wait_for_timeout(3000)

        except Exception as e:
            print(f"Aviso durante login: {e}")

    def _extract_modules_and_lessons(self, page) -> dict[str, list[str]]:
        """Mapeia os links das aulas agrupados e ordenados pelos nomes dos seus Módulos."""
        content = page.content()
        soup = BeautifulSoup(content, "html.parser")
        
        structure = {}
        current_module = "Geral"

        sections = soup.find_all(['div', 'section', 'ul', 'ol'], class_=re.compile(r'module|section|topic|curriculum|accordion', re.I))

        if sections:
            for sec in sections:
                header = sec.find(['h2', 'h3', 'h4', 'h5', 'strong', 'span', 'button'], class_=re.compile(r'title|header|heading|name', re.I))
                mod_name = header.get_text(strip=True) if header else current_module
                mod_name = sanitize_filename(mod_name) or "Módulo Geral"

                links = []
                for a in sec.find_all("a", href=True):
                    href = a["href"]
                    if any(key in href for key in ["/aula/", "/lesson/", "/topico/", "/topic/"]):
                        if href not in links and href != self.url:
                            links.append(href)

                if links and mod_name not in structure:
                    structure[mod_name] = links

        if not structure:
            all_links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if any(key in href for key in ["/aula/", "/lesson/", "/topico/", "/topic/"]):
                    if href not in all_links and href != self.url:
                        all_links.append(href)

            structure["Conteúdo do Curso"] = all_links if all_links else [self.url]

        return structure

    def _extract_media_from_page(self, page, target_url: str) -> list[str]:
        """Acessa a aula e escuta o tráfego de rede para capturar URLs de mídia."""
        captured_urls = set()

        def handle_response(response):
            u = response.url.lower()
            if any(k in u for k in [".m3u8", "pandavideo.com.br", "player.vimeo.com/video/", "b-cdn.net", "vdocipher"]):
                if not any(ign in u for ign in [".png", ".jpg", ".js", ".css", "analytics"]):
                    captured_urls.add(response.url)
            elif ".mp4" in u and "blob:" not in u:
                if not any(ign in u for ign in [".png", ".jpg", ".js", ".css"]):
                    captured_urls.add(response.url)

        page.on("response", handle_response)

        try:
            page.goto(target_url, timeout=45000, wait_until="domcontentloaded")
            page.wait_for_timeout(3500)
            page.evaluate("window.scrollBy(0, 300)")
            page.wait_for_timeout(1000)

            for frame in page.frames:
                src = frame.url
                if any(p in src.lower() for p in ["vimeo", "youtube", "pandavideo", "b-cdn", "vdocipher", "player"]):
                    captured_urls.add(src)

            content = page.content()
            soup = BeautifulSoup(content, "html.parser")
            for tag in soup.find_all(["iframe", "video", "source"]):
                src = tag.get("src") or tag.get("data-src") or ""
                if src:
                    if src.startswith("//"):
                        src = "https:" + src
                    if any(p in src.lower() for p in ["vimeo", "youtube", "pandavideo", "b-cdn", "player", "m3u8", "mp4"]):
                        captured_urls.add(src)

        except Exception as e:
            print(f"Erro ao acessar {target_url}: {e}")

        if not captured_urls:
            captured_urls.add(target_url)

        return list(captured_urls)

    def _download_target(self, target_url: str, current_idx: int, total_items: int, save_dir: str) -> tuple[bool, str]:
        """Executa o download via yt-dlp limpando códigos ANSI da interface."""
        downloaded_file_title = f"Vídeo {current_idx}"

        def _progress_hook(d):
            nonlocal downloaded_file_title
            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes', 0)
                if total > 0:
                    percent = (downloaded / total) * 100
                    speed = strip_ansi(d.get('_speed_str', '')).strip()
                    self.progress_signal.emit(
                        percent, 
                        f"Baixando vídeo {current_idx}/{total_items}: {percent:.1f}% ({speed})"
                    )
            elif d['status'] == 'finished':
                filename = os.path.basename(d.get('filename', ''))
                if filename:
                    downloaded_file_title = os.path.splitext(filename)[0]
                self.progress_signal.emit(100.0, f"Vídeo {current_idx}/{total_items} baixado. Avançando...")

        ydl_opts = {
            'outtmpl': os.path.join(save_dir, '%(title)s.%(ext)s'),
            'progress_hooks': [_progress_hook],
            'quiet': True,
            'no_warnings': True,
            'no_color': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://universotecnico.com/',
            }
        }

        if self.is_audio_only:
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        else:
            ydl_opts['format'] = 'bestvideo+bestaudio/best'

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(target_url, download=True)
                if info and 'title' in info:
                    downloaded_file_title = info['title']
            return True, downloaded_file_title
        except Exception as e:
            print(f"Erro ao baixar {target_url}: {e}")
            return False, downloaded_file_title

    def run(self):
        if not HAS_PLAYWRIGHT:
            self.finished_signal.emit(False, "Playwright não está instalado.")
            return

        success_count = 0

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                context = browser.new_context()
                page = context.new_page()

                self._perform_inpage_login(page)

                if self.is_mapping:
                    self.progress_signal.emit(20.0, "Mapeando estrutura de módulos e aulas...")
                    structure = self._extract_modules_and_lessons(page)

                    total_lessons = sum(len(links) for links in structure.values())
                    self.progress_signal.emit(25.0, f"Encontradas {total_lessons} aulas em {len(structure)} módulo(s).")

                    global_idx = 1
                    for mod_idx, (module_name, lesson_links) in enumerate(structure.items(), start=1):
                        # Nomeia e numera sequencialmente a pasta do módulo (ex: "01 - Começamos do zero")
                        numbered_module_name = f"{mod_idx:02d} - {sanitize_filename(module_name)}"
                        module_dir = os.path.join(self.output_path, numbered_module_name)
                        os.makedirs(module_dir, exist_ok=True)

                        for link in lesson_links:
                            base_percent = 25.0 + ((global_idx - 1) / total_lessons * 70.0)
                            self.progress_signal.emit(base_percent, f"Acessando aula {global_idx}/{total_lessons} ({numbered_module_name})...")
                            
                            extracted_urls = self._extract_media_from_page(page, link)
                            
                            for m_url in extracted_urls:
                                ok, file_title = self._download_target(m_url, global_idx, total_lessons, module_dir)
                                if ok:
                                    success_count += 1
                                    self.item_completed_signal.emit(file_title, module_dir, "Concluído")
                                    break
                            
                            global_idx += 1

                else:
                    self.progress_signal.emit(30.0, "Extraindo mídia da página...")
                    os.makedirs(self.output_path, exist_ok=True)
                    extracted_urls = self._extract_media_from_page(page, self.url)
                    for m_url in extracted_urls:
                        ok, file_title = self._download_target(m_url, 1, 1, self.output_path)
                        if ok:
                            success_count += 1
                            self.item_completed_signal.emit(file_title, self.output_path, "Concluído")
                            break

                browser.close()

            if success_count > 0:
                self.finished_signal.emit(True, f"{success_count} vídeo(s) baixado(s) com sucesso!")
            else:
                self.finished_signal.emit(False, "Falha ao realizar o download das aulas.")

        except Exception as e:
            self.finished_signal.emit(False, f"Erro durante a execução: {str(e)}")


class UniversoView(QWidget):
    """View do conector Universo Técnico."""

    def __init__(self, parent: QWidget | None = None, downloads_view: QWidget | None = None) -> None:
        super().__init__(parent)
        self.downloads_view = downloads_view
        self.worker = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        # Header
        header_layout = QVBoxLayout()
        header_layout.setSpacing(2)
        lbl_title = QLabel("Conector Universo Técnico")
        lbl_title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {ThemeColors.TEXT};")
        lbl_desc = QLabel("Capture, extraia e gerencie conteúdos diretamente do Universo Técnico.")
        lbl_desc.setStyleSheet(f"font-size: 12px; color: {ThemeColors.TEXT_SECONDARY};")
        header_layout.addWidget(lbl_title)
        header_layout.addWidget(lbl_desc)
        main_layout.addLayout(header_layout)

        # Grid
        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)
        main_layout.addLayout(grid_layout)

        # Captura
        frame_capture = QFrame()
        frame_capture.setFrameShape(QFrame.Shape.StyledPanel)
        grid_layout.addWidget(frame_capture, 0, 0)

        cap_layout = QVBoxLayout(frame_capture)
        cap_layout.setContentsMargins(10, 10, 10, 10)
        cap_layout.setSpacing(8)

        lbl_cap_title = QLabel("🔗 Captura de Mídia - Universo Técnico")
        lbl_cap_title.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {ThemeColors.TEXT};")
        cap_layout.addWidget(lbl_cap_title)

        self.txt_url = QLineEdit()
        self.txt_url.setPlaceholderText("Cole o link do vídeo, aula ou curso aqui...")
        cap_layout.addWidget(self.txt_url)

        qual_layout = QHBoxLayout()
        qual_layout.addWidget(QLabel("Qualidade:"))
        self.cb_quality = QComboBox()
        self.cb_quality.addItems(["Vídeo - Max Qualidade (MP4)", "Apenas Áudio (MP3)", "Vídeo - 720p (MP4)"])
        qual_layout.addWidget(self.cb_quality)
        cap_layout.addLayout(qual_layout)

        btn_layout = QHBoxLayout()
        self.btn_single = QPushButton("⚡ Baixar Mídia Avulsa")
        self._style_button_primary(self.btn_single)
        self.btn_single.clicked.connect(self._start_download_single)

        self.btn_map = QPushButton("🗺️ Mapear e Baixar Curso / Playlist")
        self._style_button_success(self.btn_map)
        self.btn_map.clicked.connect(self._start_map_and_download)

        btn_layout.addWidget(self.btn_single)
        btn_layout.addWidget(self.btn_map)
        cap_layout.addLayout(btn_layout)

        # Autenticação
        frame_auth = QFrame()
        frame_auth.setFrameShape(QFrame.Shape.StyledPanel)
        grid_layout.addWidget(frame_auth, 1, 0)

        auth_layout = QVBoxLayout(frame_auth)
        auth_layout.setContentsMargins(10, 10, 10, 10)

        lbl_auth_title = QLabel("🔐 Autenticação (Áreas Pagas / Privadas)")
        lbl_auth_title.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {ThemeColors.TEXT};")
        auth_layout.addWidget(lbl_auth_title)

        auth_form = QFormLayout()
        self.txt_user = QLineEdit()
        self.txt_user.setPlaceholderText("E-mail / Usuário")
        self.txt_pass = QLineEdit()
        self.txt_pass.setPlaceholderText("Senha")
        self.txt_pass.setEchoMode(QLineEdit.EchoMode.Password)
        auth_form.addRow("E-mail / Usuário", self.txt_user)
        auth_form.addRow("Senha", self.txt_pass)
        auth_layout.addLayout(auth_form)

        # Pasta de Destino
        frame_dest = QFrame()
        frame_dest.setFrameShape(QFrame.Shape.StyledPanel)
        grid_layout.addWidget(frame_dest, 2, 0)

        dest_layout = QVBoxLayout(frame_dest)
        dest_layout.setContentsMargins(10, 10, 10, 10)

        lbl_dest_title = QLabel("📁 Pasta de Destino")
        lbl_dest_title.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {ThemeColors.TEXT};")
        dest_layout.addWidget(lbl_dest_title)

        dest_box = QHBoxLayout()
        default_dir = os.path.join(os.path.expanduser("~"), "Downloads", "PRT_Nexus")
        self.txt_dest_path = QLineEdit(default_dir)
        self.btn_browse = QPushButton("Alterar")
        self.btn_browse.clicked.connect(self._on_browse_folder)
        dest_box.addWidget(self.txt_dest_path)
        dest_box.addWidget(self.btn_browse)
        dest_layout.addLayout(dest_box)

        # Organização de Pastas
        frame_org = QFrame()
        frame_org.setFrameShape(QFrame.Shape.StyledPanel)
        grid_layout.addWidget(frame_org, 0, 1, 3, 1)

        org_layout = QVBoxLayout(frame_org)
        org_layout.setContentsMargins(10, 10, 10, 10)

        lbl_org_title = QLabel("🗂️ Organização de Pastas (Curso / Playlist)")
        lbl_org_title.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {ThemeColors.TEXT};")
        org_layout.addWidget(lbl_org_title)

        org_form = QFormLayout()
        self.txt_course_name = QLineEdit()
        self.txt_course_name.setPlaceholderText("Nome do Conteúdo / Curso / Playlist")
        self.txt_mod_name = QLineEdit()
        self.txt_mod_name.setPlaceholderText("Organizado Automaticamente por Módulo")
        self.txt_mod_name.setReadOnly(True)
        self.txt_item_name = QLineEdit()
        self.txt_item_name.setPlaceholderText("Extração Sequencial de Vídeos")
        self.txt_item_name.setReadOnly(True)

        org_form.addRow("Nome do Conteúdo", self.txt_course_name)
        org_form.addRow("Estrutura", self.txt_mod_name)
        org_form.addRow("Mídias", self.txt_item_name)
        org_layout.addLayout(org_form)
        org_layout.addStretch()

        # Barra de Progresso Ampliada
        frame_prog = QFrame()
        frame_prog.setFrameShape(QFrame.Shape.StyledPanel)
        main_layout.addWidget(frame_prog)

        prog_layout = QHBoxLayout(frame_prog)
        prog_layout.setContentsMargins(10, 6, 10, 6)
        self.lbl_status = QLabel("Aguardando link de download...")
        self.lbl_status.setStyleSheet(f"font-size: 11px; color: {ThemeColors.TEXT_SECONDARY};")
        self.lbl_status.setMinimumWidth(380)  # Garante comprimento suficiente para exibir a velocidade completa

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(12)
        prog_layout.addWidget(self.lbl_status, stretch=2)
        prog_layout.addWidget(self.progress_bar, stretch=3)

        # Tabela
        frame_table = QFrame()
        frame_table.setFrameShape(QFrame.Shape.StyledPanel)
        main_layout.addWidget(frame_table, stretch=1)

        tbl_layout = QVBoxLayout(frame_table)
        tbl_layout.setContentsMargins(10, 10, 10, 10)

        lbl_tbl_title = QLabel("📦 Mídias Concluídas do Universo Técnico")
        lbl_tbl_title.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {ThemeColors.TEXT};")
        tbl_layout.addWidget(lbl_tbl_title)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["#", "Título / Nome do Arquivo", "Caminho Salvo", "Status"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(3, 120)
        self.table.verticalHeader().setVisible(False)
        tbl_layout.addWidget(self.table)

        self._apply_qss()

    def _on_browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Pasta", self.txt_dest_path.text())
        if folder:
            self.txt_dest_path.setText(folder)

    def _add_completed_item_to_table(self, title: str, path: str, status: str) -> None:
        """Adiciona dinamicamente cada arquivo concluído com alinhamento centralizado nas colunas '#' e 'Status'."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        item_idx = QTableWidgetItem(str(row + 1))
        item_idx.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        item_title = QTableWidgetItem(title)
        item_path = QTableWidgetItem(path)

        item_status = QTableWidgetItem(status)
        item_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        self.table.setItem(row, 0, item_idx)
        self.table.setItem(row, 1, item_title)
        self.table.setItem(row, 2, item_path)
        self.table.setItem(row, 3, item_status)

    def _start_download_single(self) -> None:
        url = self.txt_url.text().strip()
        if not url:
            self.lbl_status.setText("Erro: Insira uma URL para a mídia avulsa.")
            return

        dest_dir = self.txt_dest_path.text()
        self._run_download_worker(url, dest_dir, is_mapping=False)

    def _start_map_and_download(self) -> None:
        url = self.txt_url.text().strip()
        if not url:
            self.lbl_status.setText("Erro: Insira uma URL de curso/playlist.")
            return

        course_title = "Universo Técnico - Curso Extraído"
        self.txt_course_name.setText(course_title)

        base_path = os.path.join(self.txt_dest_path.text(), course_title)
        self._run_download_worker(url, base_path, is_mapping=True)

    def _run_download_worker(self, url: str, target_dir: str, is_mapping: bool) -> None:
        self.btn_single.setEnabled(False)
        self.btn_map.setEnabled(False)
        self.lbl_status.setText("Iniciando Chromium...")
        self.progress_bar.setValue(0)

        is_audio = "Áudio" in self.cb_quality.currentText()
        user = self.txt_user.text().strip()
        pwd = self.txt_pass.text().strip()

        self.worker = DownloadWorker(url, target_dir, is_audio, user, pwd, is_mapping=is_mapping)
        self.worker.progress_signal.connect(self._update_progress)
        self.worker.item_completed_signal.connect(self._add_completed_item_to_table)
        self.worker.finished_signal.connect(self._on_download_finished)
        self.worker.start()

    def _update_progress(self, percent: float, status_text: str) -> None:
        self.progress_bar.setValue(int(percent))
        self.lbl_status.setText(status_text)

    def _on_download_finished(self, success: bool, message: str) -> None:
        self.btn_single.setEnabled(True)
        self.btn_map.setEnabled(True)
        self.lbl_status.setText(message)
        if success:
            self.progress_bar.setValue(100)
        else:
            self.progress_bar.setValue(0)

    def _style_button_primary(self, btn: QPushButton) -> None:
        btn.setStyleSheet(f"background-color: {ThemeColors.PRIMARY}; color: white; border-radius: 4px; padding: 6px 12px; font-weight: bold;")

    def _style_button_success(self, btn: QPushButton) -> None:
        btn.setStyleSheet(f"background-color: {ThemeColors.SUCCESS}; color: white; border-radius: 4px; padding: 6px 12px; font-weight: bold;")

    def _apply_qss(self) -> None:
        self.setStyleSheet(f"""
            QWidget {{ background-color: {ThemeColors.BACKGROUND}; color: {ThemeColors.TEXT}; font-family: 'Segoe UI', sans-serif; }}
            QFrame {{ background-color: {ThemeColors.CARD}; border: 1px solid {ThemeColors.BORDER}; border-radius: 8px; }}
            QLineEdit, QComboBox {{ background-color: {ThemeColors.BACKGROUND}; border: 1px solid {ThemeColors.BORDER}; border-radius: 4px; padding: 5px 8px; color: {ThemeColors.TEXT}; }}
            QTableWidget {{ background-color: transparent; border: none; gridline-color: {ThemeColors.BORDER}; }}
            QHeaderView::section {{ background-color: transparent; border-bottom: 1px solid {ThemeColors.BORDER}; color: {ThemeColors.TEXT}; font-weight: bold; }}
            QProgressBar {{ background-color: {ThemeColors.BACKGROUND}; border: 1px solid {ThemeColors.BORDER}; border-radius: 6px; text-align: center; }}
            QProgressBar::chunk {{ background-color: {ThemeColors.SUCCESS}; border-radius: 5px; }}
        """)