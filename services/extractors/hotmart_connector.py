import json
import os
import re
import time
import unicodedata

import requests
from PySide6.QtCore import QMutex, QThread, QWaitCondition, Signal
from selenium import webdriver
from selenium.webdriver.common.by import By

try:
    import yt_dlp
except ImportError:
    yt_dlp = None


class DownloadCancelado(Exception):
    pass


NAVEGACAO = "https://api-club-course-consumption-gateway.hotmart.com/v1/navigation"
AULA = "https://api-club-course-consumption-gateway.hotmart.com/v1/lesson"
ANEXO = "https://api-club-hot-club-api.cb.hotmart.com/rest/v3/attachment"


def limpar_nome(texto):
    texto_limpo = re.sub(r'[\\/*?:"<>|]', "", texto or "")
    return re.sub(r"\s+", " ", texto_limpo).strip() or "Aula"


def normalizar(texto):
    base = unicodedata.normalize("NFKD", texto or "")
    base = "".join(c for c in base if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", base).strip().lower()


def subdominio_de(url):
    match = re.search(r"https?://([^.]+)\.club\.hotmart\.com", url or "", re.I)
    if match and match.group(1).lower() not in ("www", "club"):
        return match.group(1)
    match = re.search(r"/club/([^/?#]+)", url or "", re.I)
    if match:
        return match.group(1)
    return ""


def produto_de(url):
    match = re.search(r"/products/(\d+)", url or "", re.I)
    return match.group(1) if match else ""


def hash_de(url):
    match = re.search(r"/content/([^/?#]+)", url or "", re.I)
    return match.group(1) if match else ""


def texto_sem_html(html):
    sem_tag = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", sem_tag).strip()


class HotmartWorker(QThread):
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
        self._pausado = False
        self._cancelado = False
        self._mutex = QMutex()
        self._condicao = QWaitCondition()
        self.relatorio_txt = []
        self._sessao = requests.Session()
        self._driver = None
        self._slug = ""
        self._produto = ""

    def run(self):
        driver = None
        try:
            if not self.url or not self.email or not self.senha:
                self.concluido.emit(False, "Preencha o link do curso, o e-mail e a senha.")
                return
            os.makedirs(self.destino, exist_ok=True)
            self.progresso.emit("A abrir o Chrome...", 5)
            driver = self._abrir_chrome()
            self.progresso.emit("A abrir a Hotmart...", 12)
            driver.get(self.url)
            self._entrar(driver)
            if self._cancelado:
                return
            if "sso.hotmart.com" in driver.current_url.lower():
                driver.get(self.url)
            time.sleep(4)
            self._driver = driver
            self._slug = subdominio_de(driver.current_url) or subdominio_de(self.url)
            self._produto = produto_de(driver.current_url) or produto_de(self.url)
            if not self._slug:
                self.concluido.emit(
                    False,
                    "Não achei o curso nesse link. Cole o endereço da área de membros, aquele que abre depois de Acessar.",
                )
                return
            self.progresso.emit("A ler o menu do curso...", 30)
            self._montar_sessao(driver)
            hash_aula = hash_de(self.url)
            if self.modo_avulso and hash_aula:
                nome_curso = self._nome_do_curso({}, self._titulo_na_pagina(driver))
                titulo = (self.opcoes.get("nome_aula") or "").strip() or "Aula"
                aulas = [{
                    "num_mod": 1,
                    "titulo_mod": nome_curso,
                    "num_aula": 1,
                    "titulo": limpar_nome(titulo),
                    "hash": hash_aula,
                }]
            else:
                nome_curso, aulas = self._menu_do_curso(driver)
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
                status = self._baixar_aula(driver, aula, nome_curso, indice, total)
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
        except Exception as erro:
            self.concluido.emit(False, f"Erro no conector da Hotmart: {erro}")
        finally:
            if driver:
                driver.quit()

    def _abrir_chrome(self):
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-notifications")
        options.add_argument("--mute-audio")
        options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
        perfil = os.path.join(os.path.expanduser("~"), ".prt_nexus", "hotmart_chrome")
        os.makedirs(perfil, exist_ok=True)
        options.add_argument(f"--user-data-dir={perfil}")
        return webdriver.Chrome(options=options)

    def _entrar(self, driver):
        self.progresso.emit("A entrar na conta...", 18)
        email = self._esperar_campo(
            driver,
            "input[type='email'], input[name='username'], input[name='email']",
            20,
        )
        if email is None:
            if self._ja_entrou(driver):
                return
            raise RuntimeError("A tela de login da Hotmart não abriu.")
        email.clear()
        email.send_keys(self.email)
        senha = self._esperar_campo(driver, "input[type='password']", 8)
        if senha is None:
            self._clicar_continuar(driver)
            senha = self._esperar_campo(driver, "input[type='password']", 30)
        if senha is not None:
            senha.clear()
            senha.send_keys(self.senha)
            self._clicar_continuar(driver)
        self.progresso.emit("Aguardando a Hotmart liberar a conta...", 24)
        fora_do_login = 0
        while not self._cancelado:
            if self._ja_entrou(driver):
                fora_do_login += 1
                if fora_do_login >= 3:
                    return
            else:
                fora_do_login = 0
                aviso = "Cole o código do e-mail na janela do Chrome. Ela fica aberta."
                if not self._pediu_verificacao(driver):
                    aviso = "Se a Hotmart pedir código ou captcha, termine na janela do Chrome. Ela fica aberta."
                self.progresso.emit(aviso, 24)
            time.sleep(1)
        return

    def _esperar_campo(self, driver, seletor, segundos):
        limite = time.time() + segundos
        while time.time() < limite and not self._cancelado:
            campos = [
                campo for campo in driver.find_elements(By.CSS_SELECTOR, seletor)
                if campo.is_displayed()
            ]
            if campos:
                return campos[0]
            if self._pediu_verificacao(driver):
                self.progresso.emit(
                    "Termine a verificação na janela do Chrome. Ela fica aberta.",
                    20,
                )
                limite = max(limite, time.time() + 30)
            time.sleep(0.5)
        return None

    def _pediu_verificacao(self, driver):
        try:
            texto = driver.execute_script("return document.body ? document.body.innerText : ''") or ""
            texto = texto.lower()
        except Exception:
            return False
        sinais = (
            "enviamos um código", "enviamos um codigo", "código de verificação",
            "codigo de verificacao", "digite o código", "digite o codigo",
            "confira seu e-mail", "confira o seu e-mail", "não sou um robô",
        )
        if any(sinal in texto for sinal in sinais):
            return True
        try:
            campos = driver.find_elements(
                By.CSS_SELECTOR,
                "input[inputmode='numeric'], input[autocomplete='one-time-code'], input[name*='code'], input[id*='code']",
            )
            return any(campo.is_displayed() for campo in campos)
        except Exception:
            return False

    def _ja_entrou(self, driver):
        try:
            atual = driver.current_url.lower()
        except Exception:
            return False
        if "sso.hotmart.com" in atual:
            return False
        if "/login" in atual and "callback" not in atual:
            return False
        return True

    def _clicar_continuar(self, driver):
        for botao in driver.find_elements(By.CSS_SELECTOR, "button"):
            texto = (botao.text or "").strip().lower()
            if not botao.is_displayed():
                continue
            if botao.get_attribute("type") == "submit" or texto in (
                "entrar", "log in", "login", "continuar", "continue", "acessar", "próximo", "proximo",
            ):
                driver.execute_script("arguments[0].click();", botao)
                return

    def _montar_sessao(self, driver):
        agente = driver.execute_script("return navigator.userAgent;")
        pagina = driver.current_url or "https://hotmart.com/"
        self._sessao.headers.update({
            "User-Agent": agente,
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://hotmart.com",
            "Referer": pagina,
            "slug": self._slug,
            "x-product-id": self._produto,
        })
        for cookie in driver.get_cookies():
            self._sessao.cookies.set(cookie["name"], cookie["value"])
        vistos = self._cabecalhos_da_pagina(driver)
        if vistos.get("authorization"):
            self._sessao.headers["Authorization"] = vistos["authorization"]
        if vistos.get("slug"):
            self._slug = vistos["slug"]
            self._sessao.headers["slug"] = self._slug
        if vistos.get("x-product-id"):
            self._produto = vistos["x-product-id"]
            self._sessao.headers["x-product-id"] = self._produto

    def _cabecalhos_da_pagina(self, driver):
        achados = {}
        try:
            for entrada in driver.get_log("performance"):
                mensagem = json.loads(entrada["message"]).get("message") or {}
                pedido = (mensagem.get("params") or {}).get("request") or {}
                url = pedido.get("url") or ""
                if "hotmart.com" not in url:
                    continue
                headers = {str(chave).lower(): valor for chave, valor in (pedido.get("headers") or {}).items()}
                token = headers.get("authorization")
                if token and token.lower().startswith("bearer"):
                    achados["authorization"] = token
                if headers.get("slug"):
                    achados["slug"] = headers["slug"]
                if headers.get("x-product-id"):
                    achados["x-product-id"] = headers["x-product-id"]
        except Exception:
            pass
        if achados.get("authorization"):
            return achados
        try:
            bruto = driver.execute_script(
                "return JSON.stringify(Object.fromEntries("
                "Object.keys(localStorage).map(k => [k, localStorage.getItem(k)])));"
            )
            match = re.search(r'"(?:access_token|token|id_token)"\s*:\s*"(eyJ[^"]+)"', bruto or "")
            if match:
                achados["authorization"] = "Bearer " + match.group(1)
        except Exception:
            pass
        return achados

    def _get_json(self, url):
        resposta = self._sessao.get(url, timeout=40)
        if resposta.status_code == 200:
            return resposta.json()
        pelo_chrome = self._buscar_no_chrome(url)
        if pelo_chrome is not None:
            return pelo_chrome
        raise RuntimeError(f"A Hotmart respondeu {resposta.status_code} ao ler o curso.")

    def _buscar_no_chrome(self, url):
        if self._driver is None:
            return None
        script = """
            const url = arguments[0];
            const headers = arguments[1];
            const done = arguments[arguments.length - 1];
            fetch(url, {credentials: 'include', headers})
                .then(r => r.text().then(t => done(JSON.stringify({status: r.status, body: t}))))
                .catch(e => done(JSON.stringify({status: 0, body: String(e)})));
        """
        headers = {
            "Accept": "application/json",
            "slug": self._slug,
            "x-product-id": self._produto,
        }
        autorizacao = self._sessao.headers.get("Authorization")
        if autorizacao:
            headers["Authorization"] = autorizacao
        try:
            self._driver.set_script_timeout(45)
            bruto = self._driver.execute_async_script(script, url, headers)
            pacote = json.loads(bruto or "{}")
        except Exception:
            return None
        if pacote.get("status") != 200 or not pacote.get("body"):
            return None
        try:
            return json.loads(pacote["body"])
        except json.JSONDecodeError:
            return None

    def _nome_do_curso(self, navegacao, titulo_pagina=""):
        digitado = (self.opcoes.get("nome_conteudo") or "").strip()
        if digitado:
            return limpar_nome(digitado)
        if titulo_pagina:
            return limpar_nome(titulo_pagina)
        for chave in ("name", "courseName", "membershipName"):
            if isinstance(navegacao, dict) and navegacao.get(chave):
                return limpar_nome(navegacao[chave])
        return limpar_nome(self._slug or "Hotmart")

    def _menu_do_curso(self, driver):
        navegacao = {}
        try:
            navegacao = self._get_json(NAVEGACAO) or {}
        except Exception as erro:
            print(f"Menu da API não veio: {erro}")
        if isinstance(navegacao, list):
            navegacao = {"modules": navegacao}
        modulos = self._modulos_de(navegacao)
        aulas = self._aulas_do_menu(modulos)
        self._expandir_modulos(driver)
        titulo_pagina = self._titulo_na_pagina(driver)
        if not aulas:
            aulas = self._aulas_na_pagina(driver, titulo_pagina)
        return self._nome_do_curso(navegacao, titulo_pagina), aulas

    def _modulos_de(self, navegacao):
        if not isinstance(navegacao, dict):
            return []
        for chave in ("modules", "moduleList"):
            modulos = navegacao.get(chave)
            if isinstance(modulos, list) and modulos:
                return modulos
        dados = navegacao.get("data")
        if isinstance(dados, dict):
            return self._modulos_de(dados)
        return []

    def _titulo_na_pagina(self, driver):
        try:
            titulo = driver.execute_script(
                "const el = document.querySelector('h1');"
                "return el ? el.innerText : '';"
            )
        except Exception:
            return ""
        titulo = re.sub(r"\s+", " ", titulo or "").strip()
        if normalizar(titulo) in ("", "hotmart", "club"):
            return ""
        return titulo

    def _expandir_modulos(self, driver):
        try:
            driver.execute_script(
                """
                document.querySelectorAll('[aria-expanded="false"]').forEach((el) => {
                    const caixa = el.getBoundingClientRect();
                    if (caixa.top > 80 && caixa.width > 40) el.click();
                });
                """
            )
        except Exception:
            pass
        time.sleep(1.5)

    def _aulas_na_pagina(self, driver, titulo_curso):
        try:
            bruto = driver.execute_script(
                """
                const limpar = (texto) => (texto || '').replace(/\\s+/g, ' ').trim();
                const vistos = new Set();
                const aulas = [];
                document.querySelectorAll('a[href*="/content/"]').forEach((el) => {
                    const match = (el.href || '').match(/\\/content\\/([^/?#]+)/);
                    if (!match || vistos.has(match[1])) return;
                    let nome = limpar(el.innerText).replace(/\\b\\d{1,2}:\\d{2}(?::\\d{2})?\\b/g, '').trim();
                    if (nome.length < 2) return;
                    vistos.add(match[1]);
                    aulas.push({ hash: match[1], titulo: nome });
                });
                return aulas;
                """
            )
        except Exception:
            return []
        titulo_mod = limpar_nome(titulo_curso or "Aulas")
        aulas = []
        for indice, item in enumerate(bruto or [], 1):
            if not isinstance(item, dict) or not item.get("hash"):
                continue
            aulas.append({
                "num_mod": 1,
                "titulo_mod": titulo_mod,
                "num_aula": indice,
                "titulo": limpar_nome(item.get("titulo") or f"Aula {indice}"),
                "hash": item["hash"],
            })
        return aulas

    def _aulas_do_menu(self, modulos):
        aulas = []
        for indice_mod, modulo in enumerate(modulos, 1):
            if not isinstance(modulo, dict):
                continue
            titulo_mod = limpar_nome(modulo.get("name") or f"Modulo {indice_mod}")
            numero_mod = int(modulo.get("moduleOrder") or modulo.get("sequence") or indice_mod)
            paginas = (
                modulo.get("pages")
                or modulo.get("lessons")
                or modulo.get("contents")
                or []
            )
            for indice_aula, pagina in enumerate(paginas, 1):
                if not isinstance(pagina, dict):
                    continue
                aulas.append({
                    "num_mod": numero_mod,
                    "titulo_mod": titulo_mod,
                    "num_aula": int(pagina.get("pageOrder") or pagina.get("page_order") or indice_aula),
                    "titulo": limpar_nome(pagina.get("name") or f"Aula {indice_aula}"),
                    "hash": pagina.get("hash") or pagina.get("pageHash") or pagina.get("hashId") or "",
                })
        return aulas

    def _so_a_aula_pedida(self, aulas):
        pedido = normalizar(self.opcoes.get("nome_aula") or "")
        if not pedido:
            raise RuntimeError("Digite o nome da aula como aparece no menu.")
        exatas = [aula for aula in aulas if normalizar(aula["titulo"]) == pedido]
        if len(exatas) == 1:
            return exatas
        prefixos = [aula for aula in aulas if normalizar(aula["titulo"]).startswith(pedido)]
        if len(prefixos) == 1:
            return prefixos
        return []

    def _baixar_aula(self, driver, aula, nome_curso, indice, total):
        num = str(indice)
        titulo = aula["titulo"]
        if self.modo_avulso:
            pasta = self.destino
            nome_arquivo = titulo
        else:
            pasta, nome_arquivo = self._destino_da_aula(nome_curso, aula, indice)
        os.makedirs(pasta, exist_ok=True)
        formato = self._formato_download()
        caminho = os.path.join(pasta, f"{nome_arquivo}.{formato['ext']}")
        self.item_concluido.emit({
            "num": num,
            "titulo": titulo,
            "caminho": caminho,
            "status": "Na fila",
        })
        try:
            pagina = self._get_json(f"{AULA}/{aula['hash']}") if aula["hash"] else {}
        except Exception as erro:
            self._marcar(num, titulo, caminho, "Erro")
            print(f"Erro ao abrir a aula '{titulo}': {erro}")
            return "Erro"
        self._descricao(pagina, aula)
        if not self._pagina_tem_player(pagina):
            if os.path.exists(caminho):
                try:
                    os.remove(caminho)
                except OSError:
                    pass
            self._marcar(num, titulo, "-", "Sem vídeo")
            return "Sem vídeo"
        self._abrir_aula_no_chrome(driver, aula)
        video = self._url_do_video(pagina, driver)
        arquivos = self._anexos(pagina, pasta, forcar=not video or video == "protegido")
        if os.path.exists(caminho) and os.path.getsize(caminho) > 0:
            self.item_progresso.emit(num, 100)
            self._marcar(num, titulo, caminho, "Concluído")
            return "Concluído"
        if video == "protegido" and not arquivos:
            self._marcar(num, titulo, caminho, "Protegido")
            return "Protegido"
        if not video:
            if arquivos:
                origem = arquivos[0]
                ext = os.path.splitext(origem)[1] or ".pdf"
                destino_arquivo = os.path.join(pasta, f"{nome_arquivo}{ext}")
                if os.path.abspath(origem) != os.path.abspath(destino_arquivo) and not os.path.exists(destino_arquivo):
                    os.replace(origem, destino_arquivo)
                else:
                    destino_arquivo = origem if os.path.exists(origem) else destino_arquivo
                self.item_progresso.emit(num, 100)
                self._marcar(num, titulo, destino_arquivo, "Concluído")
                return "Concluído"
            self._marcar(num, titulo, "-", "Erro")
            return "Erro"
        try:
            self._baixar_video(video, caminho, driver, num, titulo, indice, total)
        except DownloadCancelado:
            self._cancelado = True
            return "Erro"
        except Exception as erro:
            texto = str(erro).lower()
            status = "Protegido" if any(p in texto for p in ("drm", "widevine", "protected")) else "Erro"
            self._marcar(num, titulo, caminho, status)
            print(f"Erro no Hotmart para '{titulo}': {erro}")
            return status
        self.item_progresso.emit(num, 100)
        self._marcar(num, titulo, caminho, "Concluído")
        return "Concluído"

    def _abrir_aula_no_chrome(self, driver, aula):
        self._limpar_log(driver)
        if hash_de(driver.current_url) == (aula.get("hash") or ""):
            time.sleep(3)
            return
        if hash_de(self.url) == (aula.get("hash") or ""):
            destino = self.url
        elif self._slug and self._produto and aula.get("hash"):
            destino = f"https://hotmart.com/pt-BR/club/{self._slug}/products/{self._produto}/content/{aula['hash']}"
        else:
            return
        self.progresso.emit("A abrir o player da aula...", 45)
        driver.get(destino)
        time.sleep(5)

    def _eh_link_de_video(self, endereco):
        texto = (endereco or "").lower()
        if not texto or "drive.google." in texto or "docs.google." in texto:
            return False
        return any(p in texto for p in ("vimeo.com", "youtube.com", "youtu.be", ".mp4", ".m3u8", "pandavideo", "player.hotmart"))

    def _pagina_tem_player(self, pagina):
        for media in pagina.get("mediasSrc") or []:
            if not isinstance(media, dict):
                continue
            if self._eh_link_de_video(media.get("mediaSrcUrl") or "") or media.get("mediaCode"):
                return True
        conteudo = pagina.get("content") or ""
        for origem in re.findall(r"""src=["']([^"']+)["']""", conteudo, re.I):
            if self._eh_link_de_video(origem):
                return True
        return False

    def _limpar_log(self, driver):
        try:
            driver.get_log("performance")
        except Exception:
            pass

    def _url_do_video(self, pagina, driver):
        self._referer_video = "https://hotmart.com/"
        for media in pagina.get("mediasSrc") or []:
            bruto = json.dumps(media).lower()
            if "widevine" in bruto or '"drm":true' in bruto or '"drm": true' in bruto:
                return "protegido"
            endereco = media.get("mediaSrcUrl") or ""
            if "drive.google." in endereco.lower() or "docs.google." in endereco.lower():
                continue
            if any(p in endereco.lower() for p in ("vimeo.com", "youtube.com", "youtu.be", ".mp4", ".m3u8", "pandavideo")):
                if "player.vimeo.com" not in endereco and "vimeo.com/" in endereco:
                    ident = endereco.split("vimeo.com/")[-1].split("?")[0].strip("/")
                    return f"https://player.vimeo.com/video/{ident}"
                return endereco
            if endereco:
                playlist = self._playlist_do_player(endereco)
                if playlist:
                    self._referer_video = endereco
                    return playlist
            codigo = media.get("mediaCode") or ""
            if codigo:
                embed = f"https://player.hotmart.com/embed/{codigo}"
                playlist = self._playlist_do_player(embed)
                if playlist:
                    self._referer_video = embed
                    return playlist
        visto = self._m3u8_do_chrome(driver) if self._pagina_tem_player(pagina) else ""
        if visto:
            self._referer_video = driver.current_url or self._referer_video
            return visto
        conteudo = pagina.get("content") or ""
        for origem in re.findall(r"""src=["']([^"']+)["']""", conteudo, re.I):
            if any(p in origem.lower() for p in ("vimeo.com", "youtube.com", "youtu.be", "pandavideo")):
                if "vimeo.com/" in origem and "player.vimeo.com" not in origem:
                    ident = origem.split("vimeo.com/")[-1].split("?")[0].strip("/")
                    return f"https://player.vimeo.com/video/{ident}"
                return origem
            if "hotmart" in origem.lower():
                playlist = self._playlist_do_player(origem)
                if playlist:
                    self._referer_video = origem
                    return playlist
        return ""

    def _playlist_do_player(self, player_url):
        html = ""
        try:
            resposta = self._sessao.get(
                player_url,
                headers={"Referer": "https://hotmart.com/", "Accept": "text/html"},
                timeout=40,
            )
            if resposta.status_code == 200:
                html = resposta.text
        except Exception:
            html = ""
        if not html and self._driver is not None:
            html = self._html_no_chrome(player_url)
        if not html:
            return ""
        match = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        if not match:
            direto = re.search(r"https?://[^\"'\\]+\.m3u8[^\"'\\]*", html)
            return direto.group(0).replace("\\u002F", "/").replace("\\/", "/") if direto else ""
        try:
            dados = json.loads(match.group(1))
        except json.JSONDecodeError:
            return ""
        app = ((dados.get("props") or {}).get("pageProps") or {}).get("applicationData") or {}
        if isinstance(app, str):
            try:
                app = json.loads(app)
            except json.JSONDecodeError:
                app = {}
        assets = app.get("mediaAssets") or []
        playlist = ""
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            texto = json.dumps(asset).lower()
            if "widevine" in texto or asset.get("drm") is True:
                continue
            url = asset.get("url") or asset.get("contentUrl") or ""
            if ".m3u8" in url or ".mp4" in url:
                playlist = url
                break
        if playlist:
            return playlist
        if assets:
            return "protegido"
        return ""

    def _html_no_chrome(self, url):
        script = """
            const url = arguments[0];
            const done = arguments[arguments.length - 1];
            fetch(url, {credentials: 'include'})
                .then(r => r.text().then(t => done(t)))
                .catch(() => done(''));
        """
        try:
            self._driver.set_script_timeout(40)
            return self._driver.execute_async_script(script, url) or ""
        except Exception:
            return ""

    def _m3u8_do_chrome(self, driver):
        candidatos = []
        try:
            for entrada in driver.get_log("performance"):
                mensagem = json.loads(entrada["message"]).get("message") or {}
                pedido = (mensagem.get("params") or {}).get("request") or {}
                url = pedido.get("url") or ""
                if ".m3u8" in url:
                    candidatos.append(url)
        except Exception:
            return ""
        for url in candidatos:
            if "master" in url or url.rstrip("/").endswith("playlist.m3u8"):
                return url
        return candidatos[-1] if candidatos else ""

    def _baixar_video(self, url, caminho, driver, num, titulo, indice, total):
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
        cookies = []
        if driver is not None:
            try:
                cookies = [f"{cookie['name']}={cookie['value']}" for cookie in driver.get_cookies()]
            except Exception:
                cookies = []
        if not cookies:
            cookies = [f"{cookie.name}={cookie.value}" for cookie in self._sessao.cookies]
        opcoes = {
            "outtmpl": raiz + ".%(ext)s",
            "quiet": True,
            "no_warnings": True,
            "retries": 2,
            "fragment_retries": 2,
            "http_headers": {
                "User-Agent": self._sessao.headers.get("User-Agent", ""),
                "Referer": getattr(self, "_referer_video", None) or "https://hotmart.com/",
                "Cookie": "; ".join(cookies),
            },
            "progress_hooks": [hook],
            **formato["ydl"],
        }
        with yt_dlp.YoutubeDL(opcoes) as ydl:
            ydl.download([url])
        if os.path.exists(caminho) and os.path.getsize(caminho) > 0:
            return
        pasta = os.path.dirname(caminho)
        prefixo = os.path.basename(raiz)
        for nome in os.listdir(pasta):
            if nome.startswith(prefixo) and os.path.getsize(os.path.join(pasta, nome)) > 0:
                return
        raise RuntimeError("o arquivo não foi salvo")

    def _formato_download(self):
        qualidade = self.opcoes.get("qualidade") or ""
        if "MP3" in qualidade or "Áudio" in qualidade or "Audio" in qualidade:
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
            formato = "bv*[height<=1080]+ba/b[height<=1080]/best[height<=1080]/b"
        elif "720" in qualidade:
            formato = "bv*[height<=720]+ba/b[height<=720]/best[height<=720]/b"
        else:
            formato = "bv*+ba/b"
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

    def _anexos(self, pagina, pasta, forcar=False):
        if not forcar and not self.opcoes.get("baixar_anexos"):
            return []
        salvos = []
        for anexo in pagina.get("attachments") or []:
            ident = anexo.get("fileMembershipId") or anexo.get("id")
            nome = limpar_nome(anexo.get("fileName") or anexo.get("name") or "anexo")
            if not ident:
                continue
            destino = os.path.join(pasta, nome)
            if os.path.exists(destino) and os.path.getsize(destino) > 0:
                salvos.append(destino)
                continue
            try:
                resposta = self._sessao.get(f"{ANEXO}/{ident}/download", timeout=60)
                if resposta.status_code != 200 or "json" in (resposta.headers.get("Content-Type") or ""):
                    continue
                with open(destino, "wb") as arquivo:
                    arquivo.write(resposta.content)
                salvos.append(destino)
            except Exception as erro:
                print(f"Anexo '{nome}' não baixou: {erro}")
        return salvos

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
        except Exception as erro:
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
