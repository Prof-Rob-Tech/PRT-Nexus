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
                context = self._criar_contexto(p)
                page = context.new_page()
                try:
                    page = self._entrar_no_portal(page, context)
                    if self._precisa_login_wordpress(page) and not self._esta_logado(context):
                        self.concluido.emit(
                            False,
                            "Não foi possível entrar no WordPress. Confira o login e tente de novo.",
                        )
                        return

                    self.progresso.emit("Acessando área do curso...", 30)
                    page.goto(self.url_curso, wait_until="domcontentloaded", timeout=300000)
                    page.wait_for_timeout(3000)
                    if self._precisa_login_wordpress(page) and not self._esta_logado(context):
                        self.concluido.emit(False, "A área do curso ainda pediu login. O mapeamento foi interrompido.")
                        return

                    pasta_curso = os.path.join(self.pasta_destino, "Universo Técnico - Curso Extraído")
                    os.makedirs(pasta_curso, exist_ok=True)

                    self.progresso.emit("Mapeando lista de aulas...", 45)
                    if self.modo_avulso:
                        aulas_mapeadas = [{"titulo": "Aula_Avulsa", "href": None}]
                    else:
                        aulas_mapeadas = self._mapear_aulas(page)

                    if not aulas_mapeadas:
                        vimeo_na_pagina = self._capturar_vimeo_atual(page)
                        if vimeo_na_pagina:
                            aulas_mapeadas = [{"titulo": "Aula_Avulsa", "href": None}]
                        else:
                            self.concluido.emit(False, "Nenhuma aula foi encontrada na página do curso.")
                            return

                    total_aulas = len(aulas_mapeadas)
                    videos_baixados = 0

                    for idx, aula in enumerate(aulas_mapeadas, 1):
                        nome_aula = self._limpar_nome(aula["titulo"])
                        nome_arquivo = f"{idx:02d} - {nome_aula}" if not self.modo_avulso else nome_aula
                        caminho_previsto = os.path.join(pasta_curso, f"{nome_arquivo}.mp4")

                        if not self.modo_avulso and aula.get("href"):
                            try:
                                page.goto(aula["href"], wait_until="domcontentloaded", timeout=300000)
                                page.wait_for_timeout(2500)
                            except Exception:
                                pass

                        pagina_atual = self._pagina_ativa(context, page)
                        vimeo_url = self._capturar_vimeo_atual(pagina_atual)
                        num_str = str(idx)

                        if vimeo_url:
                            videos_baixados += 1
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

                    if videos_baixados == 0:
                        self.concluido.emit(False, "Nenhum vídeo foi localizado na página.")
                        return

                    self.progresso.emit("Downloads concluídos!", 100)
                    self.concluido.emit(True, f"{videos_baixados} vídeo(s) baixado(s) com sucesso!")
                finally:
                    context.close()
                    if getattr(self, "_browser", None):
                        self._browser.close()
                        self._browser = None

        except Exception as e:
            self.concluido.emit(False, f"Erro: {str(e)}")

    def _criar_contexto(self, p):
        args = [
            "--autoplay-policy=user-gesture-required",
            "--mute-audio",
            "--disable-blink-features=AutomationControlled",
        ]
        try:
            self._browser = p.chromium.launch(channel="chrome", headless=False, args=args)
        except Exception:
            self._browser = p.chromium.launch(headless=False, args=args)
        return self._browser.new_context(
            viewport={"width": 1280, "height": 720},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
        )

    def _seletor_usuario(self):
        return "#user_login, input[name='log'], #username, input[name='username'], input[name='email'], input[type='email']"

    def _seletor_senha(self):
        return "#user_pass, input[name='pwd'], #password, input[name='password'], input[type='password']"

    def _campos_login_visiveis(self, page):
        return page.locator(self._seletor_usuario()).filter(visible=True)

    def _tem_formulario_login(self, page):
        try:
            return self._campos_login_visiveis(page).count() > 0
        except Exception:
            return False

    def _tem_cookie_teste(self, context):
        try:
            return any(c.get("name") == "wordpress_test_cookie" for c in context.cookies())
        except Exception:
            return False

    def _pagina_com_erro_cookie(self, page):
        try:
            texto = (page.inner_text("body") or "").lower()
            return "cookies" in texto and ("bloqueia" in texto or "ativar os cookies" in texto)
        except Exception:
            return False

    def _esta_logado(self, context):
        try:
            return any(
                str(c.get("name", "")).startswith("wordpress_logged_in_")
                for c in context.cookies()
            )
        except Exception:
            return False

    def _injetar_cookie_teste(self, context, page):
        try:
            page.evaluate(
                "document.cookie = 'wordpress_test_cookie=WP Cookie check; path=/; SameSite=Lax'"
            )
        except Exception:
            pass
        try:
            context.add_cookies([
                {
                    "name": "wordpress_test_cookie",
                    "value": "WP Cookie check",
                    "url": "https://universotecnico.com/wp-login.php",
                    "path": "/",
                    "secure": True,
                    "sameSite": "Lax",
                }
            ])
        except Exception:
            pass

    def _precisa_login_wordpress(self, page):
        try:
            return page.locator("#user_login").filter(visible=True).count() > 0
        except Exception:
            return False

    def _aba_apos_login(self, context, page):
        for p in context.pages:
            if p.is_closed():
                continue
            url = p.url or ""
            if "wp-login.php" not in url and not url.startswith("chrome://") and url != "about:blank":
                return p
        return page

    def _fechar_abas_de_login(self, context, page_atual):
        for p in list(context.pages):
            if p is page_atual or p.is_closed():
                continue
            if "wp-login.php" in (p.url or ""):
                try:
                    p.close()
                except Exception:
                    pass

    def _abrir_wp_login(self, page, context):
        page.goto("https://universotecnico.com/wp-login.php", wait_until="domcontentloaded", timeout=300000)
        page.wait_for_timeout(1500)
        self._injetar_cookie_teste(context, page)
        page.wait_for_timeout(300)

    def _entrar_no_portal(self, page, context):
        self.progresso.emit("Acessando portal Universo Técnico...", 10)
        self._abrir_wp_login(page, context)
        self._fazer_login_wordpress(page)
        page.wait_for_timeout(3000)

        page = self._aba_apos_login(context, page)
        self._fechar_abas_de_login(context, page)
        return page

    def _fazer_login_wordpress(self, page):
        campo_usuario = page.locator("#user_login")
        campo_senha = page.locator("#user_pass")
        campo_usuario.wait_for(state="visible", timeout=20000)

        campo_usuario.click()
        campo_usuario.fill("")
        campo_usuario.fill(self.email)
        campo_senha.click()
        campo_senha.fill("")
        campo_senha.fill(self.senha)
        page.wait_for_timeout(400)
        page.locator("#wp-submit").click()
        page.wait_for_timeout(4000)

    def _pagina_ativa(self, context, page):
        abertas = [p for p in context.pages if not p.is_closed()]
        return abertas[-1] if abertas else page

    def _mapear_aulas(self, page):
        seletores = [
            "a.ld-item-name",
            ".ld-table-list-item a",
            ".learndash-wrapper a[href*='/lessons/']",
            ".learndash-wrapper a[href*='/topic/']",
            ".llms-lesson-preview a",
            ".tutor-course-content-list-item a",
            "a[href*='/lessons/']",
            "a[href*='/lesson/']",
            "a[href*='/topico']",
            "a[href*='/aula']",
        ]
        aulas = []
        hrefs_vistos = set()
        bloqueados = ("wp-login.php", "minha-conta", "wp-admin", "logout", "cadastr")

        for seletor in seletores:
            for link in page.locator(seletor).all():
                try:
                    href = (link.get_attribute("href") or "").strip()
                    titulo = (link.text_content() or "").strip()
                    if not href or href.startswith("#") or href.startswith("javascript:"):
                        continue
                    if any(b in href.lower() for b in bloqueados):
                        continue
                    if href in hrefs_vistos:
                        continue
                    if not titulo or len(titulo) < 3:
                        continue
                    hrefs_vistos.add(href)
                    aulas.append({"titulo": titulo, "href": href})
                except Exception:
                    continue
            if aulas:
                break
        return aulas

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