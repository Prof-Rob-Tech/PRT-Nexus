import os
import subprocess
import re
from PySide6.QtCore import QThread, Signal
from playwright.sync_api import sync_playwright

class Chip7Worker(QThread):
    progresso = Signal(str, int)
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
            os.makedirs(self.pasta_destino, exist_ok=True)
            self.progresso.emit("Iniciando navegador...", 5)

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                context = browser.new_context(viewport={"width": 1280, "height": 720})
                page = context.new_page()

                # 1. Login no portal da Chip 7
                self.progresso.emit("Acessando portal Chip 7...", 10)
                page.goto("https://chip7cursos.com.br/", wait_until="domcontentloaded")
                page.wait_for_timeout(2000)

                btn_entrar = page.locator("a, button").filter(has_text=re.compile(r"ENTRAR", re.I)).first
                if btn_entrar.is_visible():
                    btn_entrar.click()
                    page.wait_for_timeout(2000)

                self.progresso.emit("Realizando login...", 20)
                page.wait_for_selector("input[type='password']", timeout=12000)

                campo_senha = page.locator("input[type='password']").first
                campo_email = page.locator("input[type='email'], input[name*='email' i], input[placeholder*='mail' i], input[placeholder*='suário' i]").first
                
                if not campo_email.is_visible():
                    campo_email = page.locator("input:visible").filter(has_not=campo_senha).first

                campo_email.click(force=True)
                campo_email.fill(self.email)
                page.wait_for_timeout(300)

                campo_senha.click(force=True)
                campo_senha.fill(self.senha)
                page.wait_for_timeout(300)

                btn_submit = page.locator("button[type='submit'], input[type='submit'], button:has-text('ENTRAR')").first
                if btn_submit.is_visible():
                    btn_submit.click()
                else:
                    campo_senha.press("Enter")

                page.wait_for_timeout(4500)

                # 2. Navegação para a aula/curso
                self.progresso.emit("Acessando área do curso...", 35)
                page.goto(self.url_curso, wait_until="domcontentloaded")
                page.wait_for_timeout(3500)

                titulo_modulo = self._extrair_titulo_modulo(page)
                pasta_modulo = os.path.join(self.pasta_destino, self._limpar_nome(titulo_modulo))
                os.makedirs(pasta_modulo, exist_ok=True)

                # 3. Mapeamento de aulas
                if self.modo_avulso:
                    aulas_mapeadas = [{"titulo": "Aula_Avulsa", "href": self.url_curso}]
                else:
                    self.progresso.emit("Mapeando lista de aulas...", 50)
                    elementos = page.locator("a").filter(has_text=re.compile(r"AULA|REPARANDO|FACE ID|MEDINDO|CIRCUITO|MÉTODOS", re.I)).all()
                    aulas_mapeadas = []
                    for elem in elementos:
                        txt = elem.text_content().strip()
                        if txt and txt not in [a["titulo"] for a in aulas_mapeadas]:
                            aulas_mapeadas.append({"titulo": txt, "href": elem.get_attribute("href") or ""})

                if not aulas_mapeadas:
                    aulas_mapeadas = [{"titulo": "Aula_01", "href": self.url_curso}]

                total_aulas = len(aulas_mapeadas)
                videos_baixados = 0

                # 4. Download individual dos vídeos Vimeo
                for idx, aula in enumerate(aulas_mapeadas, 1):
                    nome_aula = self._limpar_nome(aula["titulo"])
                    self.progresso.emit(f"Processando ({idx}/{total_aulas}): {nome_aula[:20]}...", 50 + int((idx/total_aulas)*45))

                    if not self.modo_avulso and total_aulas > 1:
                        try:
                            link = page.locator(f"a:has-text('{aula['titulo']}')").first
                            if link.is_visible():
                                link.click(force=True)
                                page.wait_for_timeout(3500)
                        except Exception:
                            pass

                    vimeo_url = self._capturar_vimeo_atual(page)

                    # Filtro de segurança: impede o envio da URL do Chip7 ao yt-dlp
                    if vimeo_url and "vimeo.com" in vimeo_url and "chip7cursos" not in vimeo_url:
                        nome_arquivo = f"{idx:02d}_{nome_aula}" if not self.modo_avulso else nome_aula
                        caminho_final = self._baixar_com_ytdlp(vimeo_url, pasta_modulo, nome_arquivo)

                        if caminho_final and os.path.exists(caminho_final):
                            videos_baixados += 1
                            self.item_concluido.emit({
                                "num": str(videos_baixados),
                                "titulo": nome_arquivo,
                                "caminho": caminho_final,
                                "status": "Concluído"
                            })

                browser.close()

                if videos_baixados == 0:
                    self.concluido.emit(False, "Nenhum vídeo do Vimeo foi localizado. Verifique se o login foi concluído com sucesso.")
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
        return re.sub(r'\s+', '_', re.sub(r'[\\/*?:"<>|]', "", texto)).strip('_')

    def _baixar_com_ytdlp(self, vimeo_url, pasta_destino, nome_arquivo):
        if "vimeo.com" not in vimeo_url or "chip7cursos" in vimeo_url:
            return None

        caminho_saida = os.path.join(pasta_destino, f"{nome_arquivo}.mp4")
        comando = [
            "yt-dlp",
            "-o", caminho_saida,
            "--referer", "https://chip7cursos.com.br/",
            vimeo_url
        ]
        res = subprocess.run(comando, capture_output=True)
        return caminho_saida if res.returncode == 0 else None