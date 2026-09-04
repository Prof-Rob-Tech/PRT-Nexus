import os
import subprocess
import re
from PySide6.QtCore import QThread, Signal

class UniversoWorker(QThread):
    progresso = Signal(str, int)
    item_progresso = Signal(str, float)
    item_concluido = Signal(dict)
    concluido = Signal(bool, str)

    def __init__(self, url_curso, email, senha, pasta_destino, modo_avulso=False):
        super().__init__()
        self.url_curso = url_curso.strip()
        self.email = email.strip()
        self.senha = senha.strip()
        self.pasta_destino = pasta_destino.strip() if pasta_destino else os.path.join(os.path.expanduser("~"), "Downloads", "PRT_Nexus")
        self.modo_avulso = modo_avulso

    def run(self):
        try:
            from playwright.sync_api import sync_playwright
            os.makedirs(self.pasta_destino, exist_ok=True)
            self.progresso.emit("Iniciando navegador...", 5)

            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=False,
                    args=["--autoplay-policy=user-gesture-required", "--mute-audio", "--no-sandbox"]
                )
                context = browser.new_context(viewport={"width": 1280, "height": 720})
                page = context.new_page()

                # 1. Login
                self.progresso.emit("Acessando portal Universo Técnico...", 10)
                page.goto("https://universotecnico.com/login", wait_until="domcontentloaded", timeout=300000)
                page.wait_for_timeout(2000)

                campo_email = page.locator("input[type='email'], input[name='email'], input[name='username']").first
                campo_senha = page.locator("input[type='password']").first

                if campo_email.is_visible():
                    campo_email.fill(self.email)
                    campo_senha.fill(self.senha)
                    page.wait_for_timeout(300)
                    campo_senha.press("Enter")
                    page.wait_for_timeout(4000)

                # 2. Navegação
                self.progresso.emit("Acessando área do curso...", 30)
                page.goto(self.url_curso, wait_until="domcontentloaded", timeout=300000)
                page.wait_for_timeout(4000)

                pasta_curso = os.path.join(self.pasta_destino, "Universo Técnico - Curso Extraído")
                os.makedirs(pasta_curso, exist_ok=True)

                # 3. Mapeamento
                self.progresso.emit("Mapeando lista de aulas...", 45)
                if self.modo_avulso:
                    aulas_mapeadas = [{"titulo": "Aula_Avulsa", "elemento": None}]
                else:
                    elementos = page.locator("a[href*='aula'], li a, .lesson-item").all()
                    aulas_mapeadas = []
                    for elem in elementos:
                        try:
                            txt = elem.text_content().strip()
                            if txt and len(txt) > 2 and txt not in [a["titulo"] for a in aulas_mapeadas]:
                                aulas_mapeadas.append({"titulo": txt, "elemento": elem})
                        except Exception:
                            pass

                if not aulas_mapeadas:
                    aulas_mapeadas = [{"titulo": "Aula_01", "elemento": None}]

                total_aulas = len(aulas_mapeadas)
                videos_baixados = 0

                # 4. Download individual com emissão imediata
                for idx, aula in enumerate(aulas_mapeadas, 1):
                    nome_aula = self._limpar_nome(aula["titulo"])
                    nome_arquivo = f"{idx:02d} - {nome_aula}" if not self.modo_avulso else nome_aula
                    caminho_previsto = os.path.join(pasta_curso, f"{nome_arquivo}.mp4")

                    if not self.modo_avulso and aula["elemento"]:
                        try:
                            aula["elemento"].click(force=True)
                            page.wait_for_timeout(2500)
                        except Exception:
                            pass

                    vimeo_url = self._capturar_vimeo_atual(page)
                    num_str = str(idx)

                    if vimeo_url:
                        videos_baixados += 1

                        # Adiciona na tabela IMEDIATAMENTE antes de começar o download
                        self.item_concluido.emit({
                            "num": num_str,
                            "titulo": nome_arquivo,
                            "caminho": caminho_previsto,
                            "status": "Baixando..."
                        })

                        caminho_final = self._baixar_com_ytdlp(
                            vimeo_url, pasta_curso, nome_arquivo, idx, total_aulas, nome_aula, num_str
                        )

                        status_final = "Concluído" if (caminho_final and os.path.exists(caminho_final)) else "Erro"

                        self.item_concluido.emit({
                            "num": num_str,
                            "titulo": nome_arquivo,
                            "caminho": caminho_previsto,
                            "status": status_final
                        })

                browser.close()

                if videos_baixados == 0:
                    self.concluido.emit(False, "Nenhum vídeo foi localizado na página.")
                    return

                self.progresso.emit("Downloads concluídos!", 100)
                self.concluido.emit(True, f"{videos_baixados} vídeo(s) baixado(s) com sucesso!")

        except Exception as e:
            self.concluido.emit(False, f"Erro: {str(e)}")

    def _capturar_vimeo_atual(self, page):
        try:
            match = re.search(r'https?://(?:player\.)?vimeo\.com/(?:video/)?\d+', page.content())
            if match:
                return match.group(0)

            for frame in page.frames:
                match_frame = re.search(r'https?://(?:player\.)?vimeo\.com/(?:video/)?\d+', frame.url)
                if match_frame:
                    return match_frame.group(0)
        except Exception:
            pass
        return None

    def _limpar_nome(self, texto):
        texto_limpo = re.sub(r'[\\/*?:"<>|]', "", texto)
        return re.sub(r'\s+', ' ', texto_limpo).strip()

    def _baixar_com_ytdlp(self, vimeo_url, pasta_destino, nome_arquivo, idx, total_aulas, nome_aula, num_str):
        caminho_saida = os.path.join(pasta_destino, f"{nome_arquivo}.mp4")
        base_progresso = 50 + int(((idx - 1) / total_aulas) * 45)
        fatia_progresso = 45 / total_aulas

        comando = [
            "yt-dlp",
            "--newline",
            "--no-colors",
            "--no-playlist",
            "--progress",
            "-o", caminho_saida,
            "--referer", "https://universotecnico.com/",
            vimeo_url
        ]

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        try:
            process = subprocess.Popen(
                comando,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                env=env,
                bufsize=1
            )

            if process.stdout:
                for line in iter(process.stdout.readline, ''):
                    if not line:
                        break
                    match = re.search(r'(\d+(?:\.\d+)?)\s*\%', line.strip())
                    if match:
                        pct_video = float(match.group(1))
                        progresso_total = int(base_progresso + (pct_video / 100.0) * fatia_progresso)
                        
                        self.progresso.emit(
                            f"Baixando ({idx}/{total_aulas}): {nome_aula[:20]}... ({pct_video:.1f}%)",
                            min(max(progresso_total, 1), 99)
                        )
                        self.item_progresso.emit(num_str, pct_video)

            process.wait()
            if process.returncode == 0 and os.path.exists(caminho_saida):
                return caminho_saida

        except Exception as e:
            print(f"Erro no download: {e}")

        return None