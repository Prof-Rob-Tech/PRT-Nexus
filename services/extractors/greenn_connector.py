import json
import os
import re
import shutil
import subprocess
import time
import unicodedata
from urllib.parse import unquote, urlparse

import requests
from PySide6.QtCore import QMutex, QThread, QWaitCondition, Signal

try:
    import yt_dlp
except ImportError:
    yt_dlp = None


class DownloadCancelado(Exception):
    pass


API = "https://api.greenn.club"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


def limpar_nome(texto):
    texto_limpo = re.sub(r'[\\/*?:"<>|]', "", texto or "")
    return re.sub(r"\s+", " ", texto_limpo).strip() or "Aula"


def normalizar(texto):
    base = unicodedata.normalize("NFKD", texto or "")
    base = "".join(c for c in base if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", base).strip().lower()


def texto_sem_html(html):
    sem_tags = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", sem_tags).strip()


class GreennWorker(QThread):
    progresso = Signal(str, int)
    velocidade = Signal(str)
    item_progresso = Signal(str, int)
    item_concluido = Signal(dict)
    concluido = Signal(bool, str)

    def __init__(self, url, email, senha, destino, modo_avulso=False, opcoes=None, parent=None):
        super().__init__(parent)
        self.url = (url or "").strip()
        self.email = (email or "").strip()
        self.senha = (senha or "").strip()
        self.destino = (destino or "").strip() or os.path.join(os.path.expanduser("~"), "Downloads", "PRT_Nexus")
        self.modo_avulso = modo_avulso
        self.opcoes = opcoes or {}
        self._token = ""
        self._course_id = ""
        self._pagina = None
        self._rota_vimeo = False
        self._sessao = requests.Session()
        self.relatorio_txt = []
        self._cancelado = False
        self._pausado = False
        self._mutex = QMutex()
        self._condicao = QWaitCondition()

    def run(self):
        try:
            if not self.email or not self.senha:
                self.concluido.emit(False, "Informe o e-mail e a senha da Greenn.")
                return
            if not self.url.startswith("http"):
                self.concluido.emit(False, "Cole o link da área de membros, como seucurso.greenn.club/curso/...")
                return
            self.progresso.emit("Abrindo a Greenn. Se aparecer captcha, resolva na janela do Chrome.", 5)
            from playwright.sync_api import sync_playwright

            with sync_playwright() as navegador:
                browser, pagina = self._abrir_chrome(navegador)
                try:
                    self._entrar(pagina)
                    self._pagina = pagina
                    self._baixar_tudo()
                finally:
                    self._pagina = None
                    browser.close()
        except DownloadCancelado:
            self.velocidade.emit("-- MiB/s | ETA: --:--")
        except Exception as erro:
            texto = str(erro).split("Call log:")[0].strip()
            if len(texto) > 220:
                texto = "A Greenn demorou para abrir o login. Tente de novo."
            self.concluido.emit(False, f"Erro no conector da Greenn: {texto}")

    def _baixar_tudo(self):
        try:
            self.progresso.emit("Lendo os módulos do curso...", 18)
            nome_api, aulas = self._menu()
            digitado = (self.opcoes.get("nome_conteudo") or "").strip()
            nome_curso = limpar_nome(digitado) if digitado else (nome_api or "Greenn Club")
            if not aulas:
                self.concluido.emit(False, "Entrei na conta, mas o menu do curso veio vazio.")
                return
            if self.modo_avulso:
                aulas = self._so_a_aula_pedida(aulas)
                if not aulas:
                    pedido = (self.opcoes.get("nome_aula") or "").strip()
                    self.concluido.emit(False, f"Não encontrei '{pedido}' no menu desse curso.")
                    return
            total = len(aulas)
            erros = 0
            sem_video = 0
            for indice, aula in enumerate(aulas, 1):
                self._checar_pausa()
                if self._cancelado:
                    break
                status = self._baixar_aula(aula, nome_curso, indice, total)
                if status == "Sem vídeo":
                    sem_video += 1
                elif status != "Concluído":
                    erros += 1
            if self._cancelado:
                self.velocidade.emit("-- MiB/s | ETA: --:--")
                return
            self._salvar_indice(nome_curso)
            self.velocidade.emit("-- MiB/s | ETA: --:--")
            self.progresso.emit("Processo concluído!", 100)
            if erros:
                self.concluido.emit(False, f"Fila concluída com {erros} aula(s) sem vídeo ou protegida(s).")
            elif sem_video:
                self.concluido.emit(
                    True,
                    f"Fila concluída: {total - sem_video} vídeo(s). {sem_video} aula(s) sem vídeo ficaram de fora.",
                )
            else:
                self.concluido.emit(True, f"Fila concluída: {total} aula(s).")
        except DownloadCancelado:
            self.velocidade.emit("-- MiB/s | ETA: --:--")

    def _abrir_chrome(self, navegador):
        try:
            browser = navegador.chromium.launch(
                channel="chrome",
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
        except Exception:
            browser = navegador.chromium.launch(headless=False)
        contexto = browser.new_context(locale="pt-BR", viewport={"width": 1280, "height": 800})
        return browser, contexto.new_page()

    def _entrar(self, pagina):
        pagina.goto(self.url, wait_until="domcontentloaded", timeout=120000)
        pagina.wait_for_timeout(1500)
        self._preencher_login(pagina)
        token = self._esperar_token(pagina.context, pagina)
        if not token:
            if "/curso/" in (pagina.url or "") or "/home" in (pagina.url or ""):
                raise RuntimeError("A página do curso abriu, mas a sessão da Greenn não ficou disponível. Tente de novo.")
            raise RuntimeError(
                "Não consegui entrar na Greenn. Se o captcha apareceu, resolva na janela do Chrome. Confira também o e-mail e a senha."
            )
        self._token = unquote(token).strip()
        self._bloquear_login_vimeo(pagina)
        self._ir_para_o_curso(pagina)

    def _preencher_login(self, pagina):
        email, senha = self._campos_login(pagina)
        self._escrever(email, self.email)
        self._escrever(senha, self.senha)
        botao = pagina.locator("button[type='submit']:visible")
        if botao.count() == 0:
            botao = pagina.get_by_role("button", name=re.compile(r"acessar|entrar|login", re.I))
        if botao.count() == 0:
            raise RuntimeError("Achei o login, mas não achei o botão de entrar.")
        try:
            pagina.wait_for_timeout(400)
            botao.first.click(timeout=8000)
        except Exception:
            senha.press("Enter")

    def _campos_login(self, pagina):
        senha = pagina.locator("input[type='password']:visible").first
        try:
            senha.wait_for(state="visible", timeout=30000)
        except Exception as erro:
            raise RuntimeError(
                "Não achei a tela de login. Cole o link da área de membros, como seucurso.greenn.club/curso/..."
            ) from erro
        formulario = pagina.locator("form").filter(
            has=pagina.locator("input[type='password']:visible")
        )
        if formulario.count():
            email = formulario.first.locator(
                "input:visible:not([type='password']):not([type='hidden']):not([type='checkbox'])"
            ).first
        else:
            email = pagina.locator(
                "input:visible:not([type='password']):not([type='hidden']):not([type='checkbox'])"
            ).first
        try:
            email.wait_for(state="visible", timeout=10000)
        except Exception as erro:
            raise RuntimeError("A tela de login abriu, mas o campo de e-mail não ficou disponível.") from erro
        return email, senha

    def _escrever(self, campo, valor):
        campo.click()
        campo.fill(valor)
        if campo.input_value() == valor:
            return
        campo.evaluate(
            """(el, valor) => {
                el.focus();
                const proto = HTMLInputElement.prototype;
                const desc = Object.getOwnPropertyDescriptor(proto, 'value');
                desc.set.call(el, valor);
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }""",
            valor,
        )

    def _esperar_token(self, contexto, pagina):
        for tentativa in range(40):
            self._checar_pausa()
            token = self._token_do_contexto(contexto, pagina)
            if token:
                return token
            atual = pagina.url or ""
            if "/curso/" in atual or "/home" in atual:
                self.progresso.emit("Conta aberta. Confirmando a sessão...", 8)
            elif self._senha_recusada(pagina):
                raise RuntimeError("E-mail ou senha da Greenn não conferem.")
            else:
                self._escolher_painel(pagina)
            pagina.wait_for_timeout(500)
            if tentativa == 20 and ("/curso/" in (pagina.url or "") or "/home" in (pagina.url or "")):
                break
        return self._token_do_contexto(contexto, pagina)

    def _token_do_contexto(self, contexto, pagina=None):
        if pagina is not None:
            token = self._token_da_pagina(pagina)
            if token:
                return token
        try:
            for cookie in contexto.cookies():
                if cookie.get("name") == "auth_greennCourse" and cookie.get("value"):
                    return cookie["value"]
        except Exception:
            return ""
        return ""

    def _token_da_pagina(self, pagina):
        try:
            valor = pagina.evaluate(
                """() => {
                    try {
                        const raiz = document.querySelector('#app');
                        const pinia = raiz && raiz.__vue_app__ && raiz.__vue_app__.config.globalProperties.$pinia;
                        const store = pinia && pinia._s && pinia._s.get('auth');
                        if (store && store.auth_greennCourse) return String(store.auth_greennCourse);
                    } catch (e) {}
                    const partes = (document.cookie || '').split(';');
                    for (const parte of partes) {
                        const item = parte.trim();
                        const pref = 'auth_greennCourse=';
                        if (item.startsWith(pref)) return decodeURIComponent(item.slice(pref.length));
                    }
                    return '';
                }""",
                timeout=3000,
            )
        except Exception:
            return ""
        return unquote((valor or "").strip())

    def _senha_recusada(self, pagina):
        try:
            if pagina.locator("input[type='password']:visible").count() == 0:
                return False
            return pagina.get_by_text(re.compile(r"usuário ou senha|usuario ou senha|senha inválid", re.I)).count() > 0
        except Exception:
            return False

    def _escolher_painel(self, pagina):
        atual = pagina.url or ""
        if "/home" in atual or "/curso/" in atual:
            return
        host = (urlparse(self.url).hostname or "").split(".")[0]
        if host in ("", "www", "login", "app", "greenn", "club", "members"):
            return
        try:
            alvo = pagina.get_by_text(host, exact=False)
            if alvo.count():
                alvo.first.click(timeout=1500)
        except Exception:
            return

    def _caminho_do_link(self):
        course_id = self._id_do_curso()
        if not course_id:
            return ""
        modulo = re.search(r"/modulo/(\d+)", self.url)
        aula = re.search(r"/aula/(\d+)", self.url)
        if modulo and aula:
            return f"/curso/{course_id}/modulo/{modulo.group(1)}/aula/{aula.group(1)}"
        if modulo:
            return f"/curso/{course_id}/modulo/{modulo.group(1)}/"
        return f"/curso/{course_id}"

    def _ir_para_o_curso(self, pagina):
        caminho = self._caminho_do_link()
        if not caminho:
            raise RuntimeError("Cole o link do curso, do módulo ou da aula, com /curso/ no endereço.")
        self._course_id = self._id_do_curso()
        self.progresso.emit("Abrindo o curso do link...", 12)
        for _ in range(20):
            atual = pagina.url or ""
            if "/home" in atual or f"/curso/{self._course_id}" in atual:
                break
            pagina.wait_for_timeout(300)
        if f"/curso/{self._course_id}" in (pagina.url or ""):
            return
        try:
            pagina.evaluate(
                """(caminho) => {
                    const raiz = document.querySelector('#app');
                    const router = raiz && raiz.__vue_app__ && raiz.__vue_app__.config.globalProperties.$router;
                    if (router) {
                        router.push(caminho);
                        return;
                    }
                    window.location.assign(caminho);
                }""",
                caminho,
            )
        except Exception:
            pagina.goto(self._origem() + caminho, wait_until="domcontentloaded", timeout=60000)
        for _ in range(25):
            if f"/curso/{self._course_id}" in (pagina.url or ""):
                return
            pagina.wait_for_timeout(400)
        try:
            card = pagina.locator(f"a[href*='/curso/{self._course_id}']")
            if card.count():
                card.first.click(timeout=4000)
                pagina.wait_for_timeout(1500)
        except Exception:
            pass
        if f"/curso/{self._course_id}" not in (pagina.url or ""):
            pagina.goto(self._origem() + caminho, wait_until="domcontentloaded", timeout=60000)

    def _origem(self):
        partes = urlparse(self.url)
        if partes.scheme and partes.netloc:
            return f"{partes.scheme}://{partes.netloc}"
        return "https://login.greenn.club"

    def _id_do_curso(self):
        match = re.search(r"/curso/(\d+)", self.url)
        return match.group(1) if match else ""

    def _get_json(self, caminho, params=None, obrigatorio=True):
        try:
            resposta = self._sessao.get(
                f"{API}{caminho}",
                params=params,
                headers={
                    "Authorization": self._token,
                    "Accept": "application/json",
                    "User-Agent": UA,
                    "Origin": self._origem(),
                    "Referer": self._origem() + "/",
                },
                timeout=40,
            )
        except requests.RequestException as erro:
            if obrigatorio:
                raise RuntimeError(f"A Greenn não respondeu: {erro}") from erro
            return None
        if resposta.status_code == 401:
            raise RuntimeError("A sessão da Greenn expirou. Entre de novo.")
        if resposta.status_code != 200:
            if obrigatorio:
                raise RuntimeError(f"A Greenn respondeu {resposta.status_code} ao ler o curso.")
            return None
        try:
            return resposta.json()
        except ValueError:
            if obrigatorio:
                raise RuntimeError("A Greenn não devolveu o menu do curso.")
            return None

    def _menu(self):
        course_id = self._id_do_curso()
        if not course_id:
            raise RuntimeError("Cole o link do curso, com /curso/ no endereço.")
        self._course_id = course_id
        dados = self._get_json(
            f"/course/{course_id}/watch",
            params=[("data[]", "course"), ("data[]", "modules")],
        )
        curso = dados.get("course") if isinstance(dados, dict) and isinstance(dados.get("course"), dict) else {}
        nome = self._nome_de(curso) or self._nome_de(dados if isinstance(dados, dict) else {})
        aulas = []
        for indice_mod, modulo in enumerate(self._modulos_de(dados), 1):
            if not isinstance(modulo, dict):
                continue
            titulo_mod = limpar_nome(self._nome_de(modulo) or f"Módulo {indice_mod}")
            mod_id = str(modulo.get("id") or indice_mod)
            extra = self._get_json(
                f"/course/{course_id}/watch",
                params=[("data[]", "currentModuleLessons"), ("current_module_id", mod_id)],
                obrigatorio=False,
            ) or {}
            for indice_aula, lesson in enumerate(self._aulas_do_modulo(modulo, extra), 1):
                if not isinstance(lesson, dict):
                    continue
                aulas.append({
                    "id": str(lesson.get("id") or lesson.get("lesson_id") or ""),
                    "mod_id": str(lesson.get("module_id") or mod_id),
                    "titulo": limpar_nome(self._nome_de(lesson) or f"Aula {indice_aula}"),
                    "titulo_mod": titulo_mod,
                    "num_mod": indice_mod,
                    "num_aula": indice_aula,
                })
        return nome, aulas

    def _modulos_de(self, dados):
        if not isinstance(dados, dict):
            return []
        if isinstance(dados.get("modules"), list):
            return dados["modules"]
        curso = dados.get("course") if isinstance(dados.get("course"), dict) else {}
        for chave in ("modules", "modulos"):
            if isinstance(curso.get(chave), list):
                return curso[chave]
        return []

    def _aulas_do_modulo(self, modulo, extra):
        for origem in (extra, modulo):
            if not isinstance(origem, dict):
                continue
            for chave in ("currentModuleLessons", "lessons", "classes", "aulas"):
                lista = origem.get(chave)
                if isinstance(lista, list) and lista:
                    return lista
        return []

    def _nome_de(self, item):
        if not isinstance(item, dict):
            return ""
        for chave in ("title", "name", "label", "titulo"):
            valor = item.get(chave)
            if isinstance(valor, str) and valor.strip():
                return valor.strip()
        return ""

    def _so_a_aula_pedida(self, aulas):
        pedido = self._chave(self.opcoes.get("nome_aula") or "")
        if not pedido:
            aula = re.search(r"/aula/(\d+)", self.url)
            if aula:
                return [item for item in aulas if item["id"] == aula.group(1)]
            return []
        exatas = [item for item in aulas if self._chave(item["titulo"]) == pedido]
        if exatas:
            return exatas
        return [item for item in aulas if pedido in self._chave(item["titulo"])]

    def _chave(self, texto):
        return re.sub(r"[^a-z0-9]+", " ", normalizar(texto)).strip()

    def _baixar_aula(self, aula, nome_curso, indice, total):
        num = str(indice)
        pasta, nome_arquivo = self._destino_da_aula(nome_curso, aula, indice)
        os.makedirs(pasta, exist_ok=True)
        extensao = "mp3" if self._qualidade_audio() else "mp4"
        caminho = os.path.join(pasta, f"{nome_arquivo}.{extensao}")
        self._marcar(num, nome_arquivo, caminho, "Baixando...")
        try:
            detalhe = self._detalhe_da_aula(aula)
            self._descricao(detalhe, aula)
            video = self._url_do_video(detalhe, aula)
            if not video:
                if os.path.exists(caminho):
                    os.remove(caminho)
                anexos = self._anexos(aula, detalhe, pasta, forcar=True)
                if anexos:
                    self._marcar(num, nome_arquivo, anexos[0], "Concluído")
                    return "Concluído"
                self._marcar(num, nome_arquivo, caminho, "Sem vídeo")
                return "Sem vídeo"
            if os.path.exists(caminho) and os.path.getsize(caminho) > 0:
                self._anexos(aula, detalhe, pasta)
                self._marcar(num, nome_arquivo, caminho, "Concluído")
                return "Concluído"
            salvo = self._baixar_video(video, caminho, num, aula["titulo"], indice, total)
            self._anexos(aula, detalhe, pasta)
            self._marcar(num, nome_arquivo, salvo or caminho, "Concluído")
            return "Concluído"
        except DownloadCancelado:
            raise
        except Exception as erro:
            print(f"Aula '{aula['titulo']}' não baixou: {erro}")
            self._marcar(num, nome_arquivo, caminho, "Erro")
            return "Erro"

    def _detalhe_da_aula(self, aula):
        dados = self._get_json(
            f"/course/{self._course_id}/module/{aula['mod_id']}/lesson/{aula['id']}",
            obrigatorio=False,
        )
        if isinstance(dados, dict) and isinstance(dados.get("lesson"), dict):
            return dados["lesson"]
        return dados if isinstance(dados, dict) else {}

    def _eh_video(self, endereco):
        texto = (endereco or "").lower()
        if not texto or "drive.google." in texto or "docs.google." in texto:
            return False
        return any(p in texto for p in ("vimeo.com", "youtube.com", "youtu.be", ".mp4", ".m3u8", "pandavideo"))

    def _url_do_video(self, detalhe, aula):
        if not isinstance(detalhe, dict):
            return ""
        tipo = str(detalhe.get("mediaType") or detalhe.get("media_type") or "").lower()
        if tipo in ("text", "quiz", "txt"):
            return ""
        source = detalhe.get("source") if isinstance(detalhe.get("source"), str) else ""
        if "drive.google." in source.lower() or "docs.google." in source.lower():
            return ""
        if tipo == "vimeo" or "vimeo.com/" in source:
            if ".m3u8" in source.lower() or ".mp4" in source.lower():
                return source
            if self._pagina is not None:
                fluxo = self._vimeo_na_aula(aula, source)
                if fluxo:
                    return fluxo
            return ""
        if tipo == "youtube" or "youtu" in source.lower():
            return source
        if ".m3u8" in source.lower() or ".mp4" in source.lower():
            return source
        if tipo == "panda" or "pandavideo" in source.lower():
            return self._hls_panda(detalhe, source)
        if self._eh_video(source):
            return source
        for chave in ("video_hls", "hls", "stream_url", "video_url", "url"):
            valor = detalhe.get(chave)
            if isinstance(valor, str) and self._eh_video(valor):
                return valor
        return ""

    def _bloquear_login_vimeo(self, pagina):
        if self._rota_vimeo:
            return

        def filtrar(route):
            pedido = route.request
            url = (pedido.url or "").lower()
            if any(trecho in url for trecho in ("/log_in", "/join", "/oauth", "/forgot_password")):
                route.abort()
                return
            frame = pedido.frame
            if (
                frame is not None
                and frame == pagina.main_frame
                and "player.vimeo.com" not in url
                and "vimeo.com" in url
            ):
                route.abort()
                return
            route.continue_()

        pagina.route("**/*vimeo.com/**", filtrar)
        self._rota_vimeo = True

    def _player_vimeo(self, source):
        match = re.search(r"vimeo\.com/(?:video/)?(\d+)", source or "")
        if not match:
            return ""
        ident = match.group(1)
        hash_pronto = re.search(r"[?&]h=([A-Za-z0-9]+)", source or "")
        if hash_pronto:
            return f"https://player.vimeo.com/video/{ident}?h={hash_pronto.group(1)}"
        try:
            resposta = requests.get(
                f"https://vimeo.com/{ident}",
                headers={"User-Agent": UA, "Referer": self._origem() + "/"},
                timeout=20,
            )
            achado = re.search(rf"player\.vimeo\.com/video/{ident}\?h=([A-Za-z0-9]+)", resposta.text)
            if achado:
                return f"https://player.vimeo.com/video/{ident}?h={achado.group(1)}"
        except requests.RequestException:
            pass
        return f"https://player.vimeo.com/video/{ident}"

    def _vimeo_na_aula(self, aula, source):
        pagina = self._pagina
        achados = {"m3u8": "", "mp4": "", "config": None}
        pendentes = []

        def ouvir(resposta):
            if resposta.status not in (200, 206):
                return
            url = (resposta.url or "").split("#")[0]
            baixo = url.lower()
            if ".m3u8" in baixo and not achados["m3u8"]:
                achados["m3u8"] = url
            elif ".mp4" in baixo and "vimeo" in baixo and not achados["mp4"]:
                achados["mp4"] = url
            elif "player.vimeo.com" in baixo and ("/video/" in baixo or "/config" in baixo):
                pendentes.append(resposta)

        pagina.on("response", ouvir)
        try:
            modulo = aula.get("mod_id") or aula.get("module_id") or ""
            ident = aula.get("id") or ""
            if not modulo or not ident:
                return ""
            destino = f"{self._origem()}/curso/{self._course_id}/modulo/{modulo}/aula/{ident}"
            self._bloquear_login_vimeo(pagina)
            pagina.goto(destino, wait_until="domcontentloaded", timeout=90000)
            if "/home" in (pagina.url or ""):
                self._ir_para_o_curso(pagina)
                if f"/curso/{self._course_id}" not in (pagina.url or ""):
                    pagina.goto(destino, wait_until="domcontentloaded", timeout=90000)
            for tentativa in range(28):
                self._checar_pausa()
                self._ler_respostas_vimeo(pendentes, achados)
                if achados["m3u8"] or achados["mp4"] or achados["config"]:
                    break
                if tentativa == 8 and "greenn" in (pagina.url or ""):
                    self._abrir_player_vimeo(pagina, source)
                pagina.wait_for_timeout(500)
            self._ler_respostas_vimeo(pendentes, achados)
        finally:
            pagina.remove_listener("response", ouvir)
        if achados["m3u8"]:
            return achados["m3u8"]
        if achados["mp4"]:
            return achados["mp4"]
        return self._midia_do_config(achados["config"])

    def _ler_respostas_vimeo(self, pendentes, achados):
        while pendentes and not (achados["m3u8"] or achados["mp4"]):
            resposta = pendentes.pop(0)
            try:
                corpo = resposta.text()
            except Exception:
                continue
            try:
                dados = json.loads(corpo)
            except ValueError:
                dados = None
            if isinstance(dados, dict) and dados.get("request"):
                achados["config"] = dados
                continue
            config = self._config_no_html(corpo)
            if isinstance(config, dict) and achados["config"] is None:
                achados["config"] = config
            elif isinstance(config, str) and config.startswith("http") and not achados["m3u8"]:
                achados["m3u8"] = config

    def _config_no_html(self, html):
        if not html:
            return None
        for marca in ("window.playerConfig =", "var config =", "config ="):
            inicio = 0
            while True:
                pos = html.find(marca, inicio)
                if pos < 0:
                    break
                dados = self._json_depois(html[pos:], marca)
                if isinstance(dados, dict) and dados.get("request"):
                    return dados
                inicio = pos + len(marca)
        achado = re.search(r"https?:\\?/\\?/[^\"'\\]+\.m3u8[^\"'\\]*", html)
        if not achado:
            return None
        return achado.group(0).replace("\\/", "/").replace("\\u0026", "&")

    def _json_depois(self, texto, marca):
        inicio = texto.find(marca)
        if inicio < 0:
            return None
        abre = texto.find("{", inicio)
        if abre < 0:
            return None
        try:
            dados, _fim = json.JSONDecoder().raw_decode(texto[abre:])
        except ValueError:
            return None
        return dados

    def _abrir_player_vimeo(self, pagina, source):
        try:
            tem_iframe = pagina.locator("iframe[src*='vimeo']").count() > 0
        except Exception:
            tem_iframe = False
        if tem_iframe:
            try:
                pagina.evaluate(
                    """() => {
                        document.querySelectorAll('iframe').forEach((frame) => {
                            const src = frame.src || '';
                            if (!src.includes('vimeo') || !frame.contentWindow) return;
                            frame.contentWindow.postMessage(JSON.stringify({method: 'play'}), '*');
                        });
                    }"""
                )
            except Exception:
                return
            return
        player = self._player_vimeo(source)
        if not player:
            return
        try:
            pagina.evaluate(
                """(url) => {
                    const antigo = document.getElementById('prt-vimeo');
                    if (antigo) antigo.remove();
                    const frame = document.createElement('iframe');
                    frame.id = 'prt-vimeo';
                    frame.src = url;
                    frame.width = '640';
                    frame.height = '360';
                    frame.setAttribute('allow', 'autoplay; fullscreen');
                    document.body.appendChild(frame);
                }""",
                player,
            )
        except Exception:
            return

    def _midia_do_config(self, config):
        if not isinstance(config, dict):
            return ""
        arquivos = ((config.get("request") or {}).get("files") or {})
        cdns = (arquivos.get("hls") or {}).get("cdns") or {}
        if isinstance(cdns, dict):
            for cdn in cdns.values():
                if isinstance(cdn, dict) and isinstance(cdn.get("url"), str) and cdn["url"].startswith("http"):
                    return cdn["url"]
        progressive = arquivos.get("progressive") or []
        if isinstance(progressive, list) and progressive:
            melhor = max(progressive, key=lambda item: (item or {}).get("height") or 0)
            if isinstance(melhor, dict) and isinstance(melhor.get("url"), str):
                return melhor["url"]
        texto = json.dumps(config)
        achado = re.search(r"https?://[^\"\\]+\.m3u8[^\"\\]*", texto)
        return achado.group(0).replace("\\u0026", "&") if achado else ""

    def _hls_panda(self, aula, source):
        if self._eh_video(source) and "pandavideo" not in source.lower():
            return source
        alvo = source if source.startswith("http") else ""
        if not alvo:
            ident = source or str(aula.get("video_external_id") or aula.get("external_id") or "")
            if ident:
                alvo = f"https://player.pandavideo.com.br/embed/?v={ident}"
        if not alvo:
            return ""
        try:
            resposta = requests.get(
                "https://api-v2.pandavideo.com/oembed",
                params={"url": alvo},
                headers={"User-Agent": UA},
                timeout=30,
            )
            dados = resposta.json() if resposta.status_code == 200 else {}
        except (requests.RequestException, ValueError):
            dados = {}
        hls = dados.get("video_hls") if isinstance(dados, dict) else ""
        if isinstance(hls, str) and hls.startswith("http"):
            return hls
        biblioteca = ""
        video = ""
        if isinstance(dados, dict):
            biblioteca = str(dados.get("library_id") or dados.get("pullzone_name") or "")
            video = str(dados.get("video_external_id") or "")
        biblioteca = biblioteca or str(aula.get("library_id") or "")
        video = video or str(aula.get("video_external_id") or "")
        if not biblioteca or not video:
            return alvo if ".m3u8" in alvo or ".mp4" in alvo else ""
        try:
            config = requests.get(
                f"https://config.tv.pandavideo.com.br/{biblioteca}/{video}.json",
                headers={"User-Agent": UA},
                timeout=30,
            )
            texto = config.text if config.status_code == 200 else ""
        except requests.RequestException:
            texto = ""
        achado = re.search(r"https?://[^\"'\s]+\.m3u8[^\"'\s]*", texto)
        if achado:
            return achado.group(0)
        achado = re.search(r"https?://[^\"'\s]+\.mp4[^\"'\s]*", texto)
        return achado.group(0) if achado else ""

    def _anexos(self, aula, detalhe, pasta, forcar=False):
        if not forcar and not self.opcoes.get("baixar_anexos"):
            return []
        salvos = []
        for arquivo in detalhe.get("attachments") or []:
            if isinstance(arquivo, dict):
                caminho = self._baixar_anexo(aula, arquivo, pasta)
                if caminho:
                    salvos.append(caminho)
        return salvos

    def _baixar_anexo(self, aula, arquivo, pasta):
        nome = limpar_nome(arquivo.get("name") or arquivo.get("title") or arquivo.get("filename") or "anexo")
        ident = str(arquivo.get("id") or "")
        if not ident:
            return ""
        destino = os.path.join(pasta, nome)
        if os.path.exists(destino) and os.path.getsize(destino) > 0:
            return destino
        try:
            resposta = self._sessao.get(
                f"{API}/course/{self._course_id}/module/{aula['mod_id']}/lesson/{aula['id']}/attachment/{ident}/download",
                headers={
                    "Authorization": self._token,
                    "User-Agent": UA,
                    "Referer": self._origem() + "/",
                },
                timeout=60,
            )
        except requests.RequestException:
            return ""
        if resposta.status_code != 200 or len(resposta.content) < 50:
            return ""
        if not os.path.splitext(nome)[1]:
            mime = str(arquivo.get("mime") or resposta.headers.get("Content-Type") or "").lower()
            if "pdf" in mime:
                destino += ".pdf"
            elif "zip" in mime:
                destino += ".zip"
        with open(destino, "wb") as saida:
            saida.write(resposta.content)
        return destino

    def _qualidade_audio(self):
        qualidade = self.opcoes.get("qualidade") or ""
        return "MP3" in qualidade or "Áudio" in qualidade or "Audio" in qualidade

    def _baixar_video(self, url, caminho, num, titulo, indice, total):
        if yt_dlp is None:
            raise RuntimeError("Instale o yt-dlp no ambiente do PRT Nexus.")
        formato = self._formato_download()
        ultima = [0]

        def hook(evento):
            if self._cancelado:
                raise DownloadCancelado()
            self._checar_pausa()
            if evento.get("status") != "downloading":
                return
            percentual = re.sub(r"\x1b\[[0-9;]*m", "", evento.get("_percent_str", "0%")).replace("%", "").strip()
            try:
                pct = int(float(percentual))
            except ValueError:
                pct = 0
            agora = time.time()
            if agora - ultima[0] < 0.2:
                return
            ultima[0] = agora
            self.item_progresso.emit(num, pct)
            global_pct = int(((indice - 1) + pct / 100) / total * 100)
            self.progresso.emit(f"Baixando ({indice}/{total}): {titulo[:40]}", min(max(global_pct, 1), 99))
            velocidade = re.sub(r"\x1b\[[0-9;]*m", "", evento.get("_speed_str", "--")).strip()
            eta = re.sub(r"\x1b\[[0-9;]*m", "", evento.get("_eta_str", "--:--")).strip()
            self.velocidade.emit(f"{velocidade} | ETA: {eta}")

        raiz, _ext = os.path.splitext(caminho)
        opcoes = {
            "outtmpl": raiz + ".%(ext)s",
            "quiet": True,
            "no_warnings": True,
            "retries": 2,
            "fragment_retries": 2,
            "http_headers": self._cabecalhos_video(url),
            "progress_hooks": [hook],
            **formato["ydl"],
        }
        ffmpeg = self._ffmpeg()
        if ffmpeg:
            opcoes["ffmpeg_location"] = ffmpeg
        with yt_dlp.YoutubeDL(opcoes) as ydl:
            ydl.download([url])
        salvo = caminho if os.path.exists(caminho) and os.path.getsize(caminho) > 0 else ""
        if not salvo:
            pasta = os.path.dirname(caminho)
            prefixo = os.path.basename(raiz)
            for nome in sorted(os.listdir(pasta)):
                candidato = os.path.join(pasta, nome)
                nome_base, _extensao = os.path.splitext(nome)
                if nome_base != prefixo or nome.endswith(".part"):
                    continue
                if os.path.isfile(candidato) and os.path.getsize(candidato) > 0:
                    salvo = candidato
                    break
        if not salvo:
            raise RuntimeError("o arquivo não foi salvo")
        self._trocar_opus_por_aac(salvo)
        return salvo

    def _cabecalhos_video(self, url):
        baixo = url.lower()
        if "pandavideo" in baixo:
            referer = "https://player.pandavideo.com.br/"
        elif "vimeo" in baixo or "vimeocdn" in baixo or "akamaized" in baixo:
            referer = "https://player.vimeo.com/"
        else:
            referer = self._origem() + "/"
        return {"User-Agent": UA, "Referer": referer}

    def _ffmpeg(self):
        achado = shutil.which("ffmpeg")
        if achado:
            return achado
        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            return ""

    def _tem_opus(self, caminho):
        tamanho = os.path.getsize(caminho)
        with open(caminho, "rb") as arquivo:
            if b"Opus" in arquivo.read(min(tamanho, 4_000_000)):
                return True
            if tamanho > 4_000_000:
                arquivo.seek(tamanho - 4_000_000)
                return b"Opus" in arquivo.read()
        return False

    def _trocar_opus_por_aac(self, caminho):
        if not self._tem_opus(caminho):
            return
        ffmpeg = self._ffmpeg()
        if not ffmpeg:
            return
        temporario = caminho + ".aac-tmp.mp4"
        resultado = subprocess.run(
            [ffmpeg, "-y", "-i", caminho, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", temporario],
            capture_output=True,
        )
        if resultado.returncode != 0 or not os.path.exists(temporario) or os.path.getsize(temporario) == 0:
            if os.path.exists(temporario):
                os.remove(temporario)
            return
        os.replace(temporario, caminho)

    def _formato_download(self):
        qualidade = self.opcoes.get("qualidade") or ""
        if self._qualidade_audio():
            return {
                "ext": "mp3",
                "ydl": {
                    "format": "ba/b",
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }],
                },
            }
        if "1080" in qualidade:
            formato = "bv*[height<=1080]+ba[acodec^=mp4a]/bv*[height<=1080]+ba/b[height<=1080]/b"
        elif "720" in qualidade:
            formato = "bv*[height<=720]+ba[acodec^=mp4a]/bv*[height<=720]+ba/b[height<=720]/b"
        else:
            formato = "bv*+ba[acodec^=mp4a]/bv*+ba/b"
        return {"ext": "mp4", "ydl": {"format": formato, "merge_output_format": "mp4"}}

    def _destino_da_aula(self, nome_curso, aula, indice_global):
        estrutura = self.opcoes.get("estrutura") or ""
        midias = self.opcoes.get("midias") or ""
        por_modulo = "Mesma Pasta" not in estrutura
        sequencial = "Original" not in midias
        pasta = os.path.join(self.destino, f"01 - {nome_curso}")
        mesmo_nome = normalizar(aula.get("titulo_mod")) == normalizar(nome_curso)
        if por_modulo and not mesmo_nome:
            pasta = os.path.join(pasta, f"{aula['num_mod']:02d} - {aula['titulo_mod']}")
        numero = aula["num_aula"] if por_modulo else indice_global
        nome = f"{numero:02d} - {aula['titulo']}" if sequencial else aula["titulo"]
        return pasta, nome

    def _descricao(self, pagina, aula):
        if not self.opcoes.get("gerar_txt"):
            return
        texto = texto_sem_html(pagina.get("content") or "")
        self.relatorio_txt.append(f"{aula['num_mod']:02d} - {aula['titulo_mod']}\n")
        self.relatorio_txt.append(f"  {aula['num_aula']:02d} - {aula['titulo']}\n")
        if texto:
            self.relatorio_txt.append(f"  {texto[:2000]}\n")
        self.relatorio_txt.append("\n")

    def _salvar_indice(self, nome_curso):
        if not self.opcoes.get("gerar_txt") or not self.relatorio_txt:
            return
        caminho = os.path.join(self.destino, "indice_e_descricao_curso.txt")
        try:
            with open(caminho, "w", encoding="utf-8") as arquivo:
                arquivo.write(f"=== {nome_curso} ===\n\n")
                arquivo.writelines(self.relatorio_txt)
        except OSError as erro:
            print(f"Erro ao salvar o índice: {erro}")

    def _marcar(self, num, titulo, caminho, status):
        self.item_progresso.emit(num, 100 if status in ("Concluído", "Erro", "Protegido", "Sem vídeo") else 0)
        self.item_concluido.emit({
            "num": num,
            "titulo": titulo,
            "caminho": caminho,
            "status": status,
        })

    def pausar(self):
        self._mutex.lock()
        self._pausado = True
        self._mutex.unlock()
        self.velocidade.emit("PAUSADO | ETA: --:--")

    def resumir(self):
        self._mutex.lock()
        self._pausado = False
        self._condicao.wakeAll()
        self._mutex.unlock()

    def cancelar(self):
        self._cancelado = True
        self._mutex.lock()
        self._pausado = False
        self._condicao.wakeAll()
        self._mutex.unlock()

    def _checar_pausa(self):
        self._mutex.lock()
        while self._pausado and not self._cancelado:
            self.velocidade.emit("PAUSADO | ETA: --:--")
            self._condicao.wait(self._mutex)
        self._mutex.unlock()
        if self._cancelado:
            raise DownloadCancelado()
