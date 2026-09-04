import os
import subprocess
import re
from PySide6.QtCore import QThread, Signal

class Chip7Worker(QThread):
    progresso = Signal(str, int)
    item_progresso = Signal(str, float)  # Novo sinal: (num_aula, porcentagem)
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
                    args=[
                        "--autoplay-policy=user-gesture-required",
                        "--mute-audio",
                        "--no-sandbox"
                    ]
                )
                context = browser.new_context(viewport={"width": 1280, "height": 720})
                page = context.new_page()

                # 1. Autenticação
                self.progresso.emit("Acessando portal Chip 7...", 10)
                page.goto("https://chip7cursos.com.br/", wait_until="domcontentloaded", timeout=300000)
                page.wait_for_timeout(2000)

                btn_entrar = page.locator("a, button, span").filter(has_text=re.compile(r"^ENTRAR$", re.I)).first
                if btn_entrar.is_visible():
                    btn_entrar.click(force=True)
                    page.wait_for_timeout(1500)

                campo_senha = page.locator("input[type='password']").first
                campo_senha.wait_for(state="visible", timeout=30000)

                inputs_visiveis = page.locator("input:visible").all()
                campo_email = None
                for inp in inputs_visiveis:
                    if inp.get_attribute("type") != "password":
                        campo_email = inp
                        break

                if campo_email:
                    campo_email.click(force=True)
                    campo_email.fill(self.email)
                    page.wait_for_timeout(300)

                campo_senha.click(force=True)
                campo_senha.fill(self.senha)
                page.wait_for_timeout(300)

                btn_submit = page.locator("button, input[type='submit'], div, a").filter(has_text=re.compile(r"^Entrar$", re.I)).last
                if btn_submit.is_visible():
                    btn_submit.click(force=True)
                else:
                    campo_senha.press("Enter")

                self.progresso.emit("Aguardando confirmação de login...", 30)
                page.wait_for_timeout(4000)

                # 2. Navegação para o curso
                self.progresso.emit("Acessando área do aluno...", 40)
                page.goto(self.url_curso, wait_until="domcontentloaded", timeout=300000)
                page.wait_for_timeout(4000)

                # 3. Diretório de saída
                titulo_modulo = self._extrair_titulo_modulo(page)
                pasta_modulo = os.path.join(self.pasta_destino, self._limpar_nome(titulo_modulo))
                os.makedirs(pasta_modulo, exist_ok=True)

                # 4. Mapeamento de aulas
                if self.modo_avulso:
                    aulas_mapeadas = [{"titulo": "Aula_Avulsa", "elemento": None}]
                else:
                    self.progresso.emit("Mapeando lista de aulas...", 55)
                    elementos = page.locator(".area-do-aluno a, .area-do-aluno li, div.cursor-pointer").all()
                    
                    if not elementos:
                        elementos = page.locator("a, div, li").filter(has_text=re.compile(r"FACE|MÉTODO|AULA|REPARANDO|MEDINDO|CIRCUITO|TRANSPLANTE|LUBAN|IPHONE", re.I)).all()

                    aulas_mapeadas = []
                    for elem in elementos:
                        try:
                            txt = elem.text_content().strip()
                            if txt and len(txt) > 3 and "\n" not in txt and txt not in [a["titulo"] for a in aulas_mapeadas]:
                                if not any(ign in txt.lower() for ign in ["área do aluno", "sair", "carrinho", "cursos", "bem vindo"]):
                                    aulas_mapeadas.append({"titulo": txt, "elemento": elem})
                        except Exception:
                            pass

                if not aulas_mapeadas:
                    aulas_mapeadas = [{"titulo": "Aula_01", "elemento": None}]

                total_aulas = len(aulas_mapeadas)
                videos_baixados = 0

                # 5. Processamento dos downloads
                for idx, aula in enumerate(aulas_mapeadas, 1):
                    nome_aula = self._limpar_nome(aula["titulo"])
                    nome_arquivo = f"{idx:02d}_{nome_aula}" if not self.modo_avulso else nome_aula
                    caminho_previsto = os.path.join(pasta_modulo, f"{nome_arquivo}.mp4")

                    if not self.modo_avulso and aula["elemento"]:
                        try:
                            aula["elemento"].click(force=True)
                            page.wait_for_timeout(2500)
                        except Exception:
                            pass

                    vimeo_url = self._capturar_vimeo_atual(page)

                    if vimeo_url and "vimeo.com" in vimeo_url and "chip7cursos" not in vimeo_url:
                        videos_baixados += 1
                        num_str = str(videos_baixados)

                        # Notifica a interface para criar a linha com a barra de progresso em 0%
                        self.item_concluido.emit({
                            "num": num_str,
                            "titulo": nome_arquivo,
                            "caminho": caminho_previsto,
                            "status": "Baixando..."
                        })

                        # Executa download transmitindo a porcentagem
                        caminho_final = self._baixar_com_ytdlp(
                            vimeo_url, 
                            pasta_modulo, 
                            nome_arquivo, 
                            idx, 
                            total_aulas, 
                            nome_aula,
                            num_str
                        )

                        status_final = "Concluído" if (caminho_final and os.path.exists(caminho_final)) else "Erro"

                        # Finaliza a barra desse vídeo
                        self.item_concluido.emit({
                            "num": num_str,
                            "titulo": nome_arquivo,
                            "caminho": caminho_previsto,
                            "status": status_final
                        })

                browser.close()

                if videos_baixados == 0:
                    self.concluido.emit(False, "Nenhum vídeo do Vimeo foi identificado na página do curso.")
                    return

                self.progresso.emit("Downloads concluídos!", 100)
                self.concluido.emit(True, f"{videos_baixados} vídeo(s) baixado(s) com sucesso!")

        except Exception as e:
            self.concluido.emit(False, f"Erro: {str(e)}")

    def _extrair_titulo_modulo(self, page):
        try:
            txt = page.locator("h1, h2, .area-do-aluno strong").first.text_content().strip()
            if txt: return txt
        except Exception:
            pass
        return "Curso_Chip7"

    def _capturar_vimeo_atual(self, page):
        try:
            match = re.search(r'https?://(?:player\.)?vimeo\.com/(?:video/)?\d+', page.content())
            if match:
                return match.group(0)

            for frame in page.frames:
                if "vimeo.com" in frame.url:
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
        if "vimeo.com" not in vimeo_url or "chip7cursos" in vimeo_url:
            return None

        caminho_saida = os.path.join(pasta_destino, f"{nome_arquivo}.mp4")
        base_progresso = 60 + int(((idx - 1) / total_aulas) * 35)
        fatia_progresso = 35 / total_aulas

        comando = [
            "yt-dlp",
            "--newline",
            "--no-colors",
            "--no-playlist",
            "--progress",
            "-o", caminho_saida,
            "--referer", "https://chip7cursos.com.br/",
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
                    line_str = line.strip()
                    match = re.search(r'(\d+(?:\.\d+)?)\s*\%', line_str)
                    if match:
                        pct_video = float(match.group(1))
                        
                        # Atualiza barra geral no rodapé
                        progresso_total = int(base_progresso + (pct_video / 100.0) * fatia_progresso)
                        msg_status = f"Baixando ({idx}/{total_aulas}): {nome_aula[:20]}... ({pct_video:.1f}%)"
                        self.progresso.emit(msg_status, min(max(progresso_total, 1), 99))

                        # Transmite porcentagem individual para a linha correspondente da tabela
                        self.item_progresso.emit(num_str, pct_video)

            process.wait()
            if process.returncode == 0 and os.path.exists(caminho_saida):
                return caminho_saida

        except Exception as e:
            print(f"Erro no download: {e}")

        return None