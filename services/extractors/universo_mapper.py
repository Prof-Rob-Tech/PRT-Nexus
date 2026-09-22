import ctypes
import os
import subprocess
import re
from PySide6.QtCore import QMutex, QThread, QWaitCondition, Signal

class UniversoWorker(QThread):
    progresso = Signal(str, int)
    item_progresso = Signal(str, float)
    item_concluido = Signal(dict)
    concluido = Signal(bool, str)
    velocidade = Signal(str)

    def __init__(self, url_curso, email, senha, pasta_destino, modo_avulso=False, opcoes=None):
        super().__init__()
        self.url_curso = url_curso.strip()
        self.email = email.strip()
        self.senha = senha.strip()
        self.pasta_destino = pasta_destino.strip() if pasta_destino else os.path.join(os.path.expanduser("~"), "Downloads", "PRT_Nexus")
        self.modo_avulso = modo_avulso
        self.opcoes = opcoes or {}
        self._erro_login = ""
        self._pausado = False
        self._mutex = QMutex()
        self._condicao = QWaitCondition()
        self._processo = None

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
                    if self._erro_login and not self._esta_logado(context):
                        self.concluido.emit(False, self._erro_login)
                        return
                    if self._precisa_login_wordpress(page) and not self._esta_logado(context):
                        self.concluido.emit(
                            False,
                            "Não foi possível entrar no WordPress. Confira o login e tente de novo.",
                        )
                        return

                    self.progresso.emit("Acessando área do curso...", 30)
                    page.goto(self.url_curso, wait_until="domcontentloaded", timeout=300000)
                    page.wait_for_timeout(3000)
                    page = self._preencher_login_se_preciso(context, page)
                    if self._erro_login and not self._esta_logado(context):
                        self.concluido.emit(False, self._erro_login)
                        return
                    if self._precisa_login_wordpress(page) and not self._esta_logado(context):
                        self.concluido.emit(False, "A área do curso ainda pediu login. O mapeamento foi interrompido.")
                        return

                    self.progresso.emit("Mapeando lista de aulas...", 45)
                    if self.modo_avulso:
                        aulas_mapeadas = [self._aula_avulsa(page)]
                    else:
                        aulas_mapeadas = self._montar_aulas_em_pastas(page)

                    if not aulas_mapeadas:
                        vimeo_na_pagina = self._capturar_vimeo_atual(page)
                        if vimeo_na_pagina:
                            aulas_mapeadas = [self._aula_avulsa(page)]
                        else:
                            self.concluido.emit(False, "Nenhuma aula foi encontrada na página do curso.")
                            return

                    total_aulas = len(aulas_mapeadas)
                    videos_baixados = 0

                    for idx, aula in enumerate(aulas_mapeadas, 1):
                        self._checar_pausa()
                        nome_aula = aula["titulo"]
                        nome_arquivo = aula["nome_arquivo"]
                        pasta_aula = aula["pasta"]
                        os.makedirs(pasta_aula, exist_ok=True)
                        caminho_previsto = os.path.join(pasta_aula, f"{nome_arquivo}.mp4")

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
                                vimeo_url, pasta_aula, nome_arquivo, idx, total_aulas, nome_aula, num_str
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
            if self._formulario_conta(page).locator("#username").filter(visible=True).count() > 0:
                return True
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
        page.goto(
            "https://universotecnico.com/cursos-ead/minha-conta/",
            wait_until="domcontentloaded",
            timeout=300000,
        )
        page.wait_for_timeout(1500)

    def _formulario_conta(self, page):
        return page.locator("form.woocommerce-form-login")

    def _texto_erro_login(self, page):
        try:
            aviso = page.locator("#login_error, .woocommerce-error")
            if aviso.count() > 0 and aviso.first.is_visible():
                return " ".join((aviso.first.inner_text() or "").split())
        except Exception:
            pass
        return ""

    def _pagina_login_aberta(self, context):
        for pagina in context.pages:
            if pagina.is_closed():
                continue
            if self._precisa_login_wordpress(pagina):
                return pagina
        return None

    def _entrar_no_portal(self, page, context):
        self.progresso.emit("Acessando portal Universo Técnico...", 10)
        self._abrir_wp_login(page, context)
        self._erro_login = self._fazer_login_wordpress(page)
        page.wait_for_timeout(1000)

        outra = self._pagina_login_aberta(context)
        if outra is not None and outra is not page:
            self.progresso.emit("Preenchendo a segunda tela de login...", 18)
            self._erro_login = self._fazer_login_wordpress(outra) or self._erro_login
            page = outra

        if self._erro_login and not self._esta_logado(context):
            return page

        page = self._aba_apos_login(context, page)
        self._fechar_abas_de_login(context, page)
        return page

    def _preencher_login_se_preciso(self, context, page):
        login = self._pagina_login_aberta(context)
        if login is None:
            return page
        self.progresso.emit("Preenchendo login da área do curso...", 32)
        self._erro_login = self._fazer_login_wordpress(login) or self._erro_login
        return self._aba_apos_login(context, login)

    def _fazer_login_wordpress(self, page):
        formulario = self._formulario_conta(page)
        if formulario.locator("#username").count() > 0:
            campo_usuario = formulario.locator("#username")
            campo_senha = formulario.locator("#password")
            botao = formulario.locator("button[name='login']")
        else:
            campo_usuario = page.locator("#user_login").first
            campo_senha = page.locator("#user_pass").first
            botao = page.locator("#wp-submit").first

        campo_usuario.wait_for(state="visible", timeout=20000)
        campo_usuario.fill(self.email)
        campo_senha.fill(self.senha)
        if campo_usuario.input_value().strip() != self.email:
            campo_usuario.fill(self.email)
        botao.click()
        try:
            page.wait_for_load_state("domcontentloaded", timeout=20000)
        except Exception:
            pass
        page.wait_for_timeout(1500)
        return self._texto_erro_login(page)

    def _pagina_ativa(self, context, page):
        abertas = [p for p in context.pages if not p.is_closed()]
        return abertas[-1] if abertas else page

    def _aula_avulsa(self, page):
        nome = self._limpar_nome(self._titulo_da_pagina(page)) or "Aula_Avulsa"
        return {
            "titulo": nome,
            "href": None,
            "nome_arquivo": nome,
            "pasta": self.pasta_destino,
        }

    def _titulo_da_pagina(self, page):
        try:
            titulo = page.evaluate(
                """() => {
                    const limpar = (texto) => (texto || "").replace(/\\s+/g, " ").trim();
                    const seletores = [
                        "h1.entry-title",
                        "h1.wp-block-post-title",
                        ".sensei-course-theme-lesson-header h1",
                        "header h1",
                        "h1",
                    ];
                    for (const seletor of seletores) {
                        const el = document.querySelector(seletor);
                        const texto = limpar(el ? el.innerText : "");
                        if (texto.length > 2) return texto;
                    }
                    const doc = limpar(document.title).split("|")[0];
                    return limpar(doc);
                }"""
            )
        except Exception:
            titulo = ""
        return (titulo or "").strip()

    def _montar_aulas_em_pastas(self, page):
        """Aplica nome, estrutura e numeração escolhidos na tela."""
        curso = self._mapear_curso(page)
        nome_digitado = (self.opcoes.get("nome_conteudo") or "").strip()
        nome_curso = self._limpar_nome(nome_digitado or curso.get("tituloCurso") or "Curso")
        pasta_curso = os.path.join(self.pasta_destino, f"01 - {nome_curso}")

        estrutura = self.opcoes.get("estrutura") or ""
        midias = self.opcoes.get("midias") or ""
        por_modulo = "Mesma Pasta" not in estrutura
        sequencial = "Original" not in midias

        aulas_mapeadas = []
        indice_global = 0
        for indice_mod, modulo in enumerate(curso.get("modulos") or [], 1):
            nome_mod = self._limpar_nome(modulo.get("titulo") or f"Modulo {indice_mod}")
            pasta_mod = os.path.join(pasta_curso, f"{indice_mod:02d} - {nome_mod}") if por_modulo else pasta_curso
            for indice_aula, aula in enumerate(modulo.get("aulas") or [], 1):
                indice_global += 1
                nome_aula = self._limpar_nome(aula.get("titulo") or f"Aula {indice_aula}")
                numero = indice_aula if por_modulo else indice_global
                nome_arquivo = f"{numero:02d} - {nome_aula}" if sequencial else nome_aula
                aulas_mapeadas.append({
                    "titulo": nome_aula,
                    "href": aula.get("href"),
                    "nome_arquivo": nome_arquivo,
                    "pasta": pasta_mod,
                })

        return aulas_mapeadas

    def _mapear_curso(self, page):
        try:
            dados = page.evaluate(
                """() => {
                    const limpar = (texto) => (texto || "").replace(/\\s+/g, " ").trim();
                    const tituloEl = document.querySelector("h1");
                    const tituloCurso = limpar(tituloEl ? tituloEl.innerText : "");
                    const modulos = [];
                    document.querySelectorAll("section.wp-block-sensei-lms-course-outline-module").forEach((secao) => {
                        const tituloElMod = secao.querySelector(".wp-block-sensei-lms-course-outline-module__title");
                        const titulo = limpar(tituloElMod ? tituloElMod.innerText : "");
                        const aulas = [];
                        secao.querySelectorAll("a.wp-block-sensei-lms-course-outline-lesson").forEach((link) => {
                            const span = link.querySelector("span");
                            const nome = limpar(span ? span.innerText : link.innerText);
                            const href = (link.href || "").trim();
                            if (nome && href) aulas.push({ titulo: nome, href });
                        });
                        if (titulo && aulas.length) modulos.push({ titulo, aulas });
                    });
                    return { tituloCurso, modulos };
                }"""
            )
        except Exception:
            dados = {"tituloCurso": "", "modulos": []}

        if dados.get("modulos"):
            return dados

        aulas = self._mapear_aulas(page)
        if not aulas:
            return dados
        return {
            "tituloCurso": dados.get("tituloCurso") or "",
            "modulos": [{"titulo": "Aulas", "aulas": aulas}],
        }

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

    def pausar(self):
        self._mutex.lock()
        self._pausado = True
        self._mutex.unlock()
        self._suspender_processo(True)
        self.velocidade.emit("PAUSADO | ETA: --:--")

    def resumir(self):
        self._suspender_processo(False)
        self._mutex.lock()
        self._pausado = False
        self._condicao.wakeAll()
        self._mutex.unlock()

    def cancelar(self):
        processo = self._processo
        if processo and processo.poll() is None:
            processo.kill()

    def _checar_pausa(self):
        self._mutex.lock()
        while self._pausado:
            self.velocidade.emit("PAUSADO | ETA: --:--")
            self._condicao.wait(self._mutex)
        self._mutex.unlock()

    def _suspender_processo(self, suspender):
        processo = self._processo
        if not processo or processo.poll() is not None or os.name != "nt":
            return
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        ntdll = ctypes.WinDLL("ntdll")
        handle = kernel32.OpenProcess(0x0800, False, processo.pid)
        if not handle:
            return
        if suspender:
            ntdll.NtSuspendProcess(handle)
        else:
            ntdll.NtResumeProcess(handle)
        kernel32.CloseHandle(handle)

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
            self._processo = process

            if process.stdout:
                for line in iter(process.stdout.readline, ''):
                    if not line:
                        break
                    linha = line.strip()
                    match = re.search(r'(\d+(?:\.\d+)?)\s*\%', linha)
                    if match:
                        pct_video = float(match.group(1))
                        progresso_total = int(base_progresso + (pct_video / 100.0) * fatia_progresso)

                        self.progresso.emit(
                            f"Baixando ({idx}/{total_aulas}): {nome_aula[:20]}... ({pct_video:.1f}%)",
                            min(max(progresso_total, 1), 99)
                        )
                        self.item_progresso.emit(num_str, pct_video)

                    vel = re.search(r'at\s+(\S+)\s+ETA\s+(\S+)', linha)
                    if vel:
                        self.velocidade.emit(f"{vel.group(1)} | ETA: {vel.group(2)}")

            process.wait()
            self._processo = None
            self.velocidade.emit("-- MiB/s | ETA: --:--")
            if process.returncode == 0 and os.path.exists(caminho_saida):
                return caminho_saida

        except Exception as e:
            print(f"Erro no download: {e}")

        return None