import os
import re
import time
import unicodedata

import requests
from PySide6.QtCore import QMutex, QThread, QWaitCondition, Signal

try:
    import yt_dlp
except ImportError:
    yt_dlp = None


class DownloadCancelado(Exception):
    pass


AUTH = "https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword"
AUTH_KEY = "AIzaSyDmOO1YAGt0X35zykOMTlolvsoBkefLKFU"
BASE = "https://admin-api.kiwify.com.br/v1/viewer"
LEGACY = "https://api.kiwify.com.br/v1/viewer"
CLUBS = "https://admin-api.kiwify.com/v1/viewer"
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


class KiwifyWorker(QThread):
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
        self._sessao = requests.Session()
        self.relatorio_txt = []
        self._cancelado = False
        self._pausado = False
        self._mutex = QMutex()
        self._condicao = QWaitCondition()

    def run(self):
        try:
            if not self.email or not self.senha:
                self.concluido.emit(False, "Informe o e-mail e a senha da Kiwify.")
                return
            course_id = self._id_do_curso()
            if not course_id:
                self.concluido.emit(False, "Cole o link do curso, como dashboard.kiwify.com.br/course/...")
                return
            self.progresso.emit("Entrando na Kiwify...", 5)
            self._entrar()
            self.progresso.emit("Lendo os módulos do curso...", 15)
            nome_api, aulas, course_id = self._menu(course_id)
            self._course_id = course_id
            digitado = (self.opcoes.get("nome_conteudo") or "").strip()
            nome_curso = limpar_nome(digitado) if digitado else (nome_api or "Kiwify")
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
        except Exception as erro:
            self.concluido.emit(False, f"Erro no conector da Kiwify: {erro}")

    def _entrar(self):
        resposta = requests.post(
            AUTH,
            params={"key": AUTH_KEY},
            json={"email": self.email, "password": self.senha, "returnSecureToken": True},
            timeout=40,
        )
        try:
            dados = resposta.json()
        except ValueError:
            dados = {}
        token = dados.get("idToken") or ""
        if resposta.status_code != 200 or not token:
            mensagem = ((dados.get("error") or {}).get("message") or "não entrou")
            raise RuntimeError(self._traduzir_login(mensagem))
        self._token = token
        self._sessao.headers.update({
            "Authorization": f"Bearer {token}",
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://dashboard.kiwify.com",
            "Referer": "https://dashboard.kiwify.com/",
        })

    def _traduzir_login(self, mensagem):
        texto = (mensagem or "").upper()
        if "INVALID_PASSWORD" in texto or "INVALID_LOGIN" in texto or "INVALID_EMAIL" in texto:
            return "E-mail ou senha da Kiwify não conferem."
        if "EMAIL_NOT_FOUND" in texto:
            return "Não achei essa conta na Kiwify."
        if "TOO_MANY_ATTEMPTS" in texto:
            return "Muitas tentativas na Kiwify. Espere um pouco e tente de novo."
        return "Não consegui entrar na Kiwify."

    def _id_do_curso(self):
        match = re.search(r"/course/([0-9a-fA-F-]{8,})", self.url)
        return match.group(1) if match else ""

    def _get_json(self, url, obrigatorio=True, headers=None):
        try:
            resposta = self._sessao.get(url, headers=headers, timeout=40)
        except requests.RequestException as erro:
            if obrigatorio:
                raise RuntimeError(f"A Kiwify não respondeu: {erro}") from erro
            return None
        if resposta.status_code == 401:
            raise RuntimeError("A sessão da Kiwify expirou. Entre de novo.")
        if resposta.status_code != 200:
            if obrigatorio:
                raise RuntimeError(f"A Kiwify respondeu {resposta.status_code} ao ler o curso.")
            return None
        try:
            return resposta.json()
        except ValueError:
            if obrigatorio:
                raise RuntimeError("A Kiwify não devolveu o menu do curso.")
            return None

    def _menu(self, course_id):
        for url in (
            f"{BASE}/courses/{course_id}/sections",
            f"{BASE}/courses/{course_id}",
            f"{LEGACY}/courses/{course_id}",
        ):
            dados = self._get_json(url, obrigatorio=False)
            nome, aulas = self._aulas_de(dados)
            if aulas:
                return nome, aulas, course_id
        real = self._curso_do_clube(course_id)
        if real and real != course_id:
            dados = self._get_json(f"{BASE}/courses/{real}/sections", obrigatorio=False)
            nome, aulas = self._aulas_de(dados)
            if aulas:
                return nome, aulas, real
        return "", [], course_id

    def _curso_do_clube(self, public_id):
        cabecalhos = {"Origin": "https://members.kiwify.com", "Referer": "https://members.kiwify.com/"}
        for url in (
            f"{CLUBS}/clubs/{public_id}/content",
            f"{CLUBS}/clubs/{public_id}/content?caipirinha=true",
        ):
            dados = self._get_json(url, obrigatorio=False, headers=cabecalhos)
            ident = self._primeiro_curso(dados)
            if ident:
                return ident
        return ""

    def _primeiro_curso(self, dados):
        if not isinstance(dados, dict):
            return ""
        data = dados.get("data") if isinstance(dados.get("data"), dict) else {}
        content = data.get("content") if isinstance(data.get("content"), dict) else {}
        for secao in content.get("sections") or []:
            if not isinstance(secao, dict):
                continue
            tipo = secao.get("type")
            for item in secao.get("items") or []:
                if not isinstance(item, dict):
                    continue
                if tipo == "courses" and item.get("id"):
                    return str(item["id"])
                if tipo == "modules" and item.get("course_id"):
                    return str(item["course_id"])
        for origem in (data.get("courses"), dados.get("courses")):
            for curso in origem or []:
                if isinstance(curso, dict) and curso.get("id"):
                    return str(curso["id"])
        todos = data.get("all_courses")
        if isinstance(todos, dict) and todos:
            return str(next(iter(todos)))
        return ""

    def _aulas_de(self, dados):
        if not isinstance(dados, dict):
            return "", []
        curso = dados.get("course") if isinstance(dados.get("course"), dict) else dados
        info = curso.get("course_info") if isinstance(curso.get("course_info"), dict) else {}
        nome = self._nome_de(curso) or self._nome_de(info)
        grupos = []
        secoes = self._lista(curso, ("sections",))
        if secoes:
            for secao in secoes:
                if not isinstance(secao, dict):
                    continue
                internos = self._lista(secao, ("modules",))
                if internos:
                    grupos.extend(item for item in internos if isinstance(item, dict))
                elif self._lista(secao, ("lessons", "contents", "items")):
                    grupos.append(secao)
        else:
            grupos = [item for item in self._lista(curso, ("modules", "moduleList")) if isinstance(item, dict)]
        aulas = []
        num_mod = 0
        for grupo in grupos:
            itens = [item for item in self._lista(grupo, ("lessons", "contents", "items")) if isinstance(item, dict)]
            if not itens:
                continue
            num_mod += 1
            titulo_mod = self._nome_de(grupo) or f"Modulo {num_mod}"
            num_aula = 0
            for item in itens:
                ident = self._id_de(item)
                if not ident:
                    continue
                num_aula += 1
                aulas.append({
                    "num_mod": num_mod,
                    "titulo_mod": titulo_mod,
                    "num_aula": num_aula,
                    "titulo": self._nome_de(item) or f"Aula {num_aula}",
                    "id": ident,
                })
        return nome, aulas

    def _lista(self, item, chaves):
        if not isinstance(item, dict):
            return []
        for chave in chaves:
            valor = item.get(chave)
            if isinstance(valor, list) and valor:
                return valor
        return []

    def _nome_de(self, item):
        if not isinstance(item, dict):
            return ""
        for chave in ("name", "title", "label"):
            valor = item.get(chave)
            if isinstance(valor, str) and valor.strip():
                return limpar_nome(valor)
        return ""

    def _id_de(self, item):
        for chave in ("id", "lesson_id", "hash"):
            valor = item.get(chave)
            if valor:
                return str(valor)
        return ""

    def _so_a_aula_pedida(self, aulas):
        pedido = self._chave(self.opcoes.get("nome_aula") or "")
        if not pedido:
            lesson = re.search(r"[?&]lesson=([0-9a-fA-F-]{8,})", self.url)
            if lesson:
                return [aula for aula in aulas if aula["id"] == lesson.group(1)]
            return []
        exatas = [aula for aula in aulas if self._chave(aula["titulo"]) == pedido]
        if exatas:
            return exatas
        return [aula for aula in aulas if pedido in self._chave(aula["titulo"])]

    def _chave(self, texto):
        return re.sub(r"[^a-z0-9]+", " ", normalizar(texto)).strip()

    def _baixar_aula(self, aula, nome_curso, indice, total):
        num = str(indice)
        titulo = aula["titulo"]
        pasta, nome_arquivo = self._destino_da_aula(nome_curso, aula, indice)
        os.makedirs(pasta, exist_ok=True)
        formato = self._formato_download()
        caminho = os.path.join(pasta, f"{nome_arquivo}.{formato['ext']}")
        self.item_concluido.emit({"num": num, "titulo": titulo, "caminho": caminho, "status": "Na fila"})
        try:
            detalhe = self._detalhe_da_aula(aula["id"])
        except Exception as erro:
            self._marcar(num, titulo, caminho, "Erro")
            print(f"Erro ao abrir a aula '{titulo}': {erro}")
            return "Erro"
        self._descricao(detalhe, aula)
        video = self._url_do_video(detalhe)
        arquivos = self._anexos(detalhe, pasta, forcar=not video)
        if not video:
            if os.path.exists(caminho):
                try:
                    os.remove(caminho)
                except OSError:
                    pass
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
            self._marcar(num, titulo, "-", "Sem vídeo")
            return "Sem vídeo"
        if os.path.exists(caminho) and os.path.getsize(caminho) > 0:
            self.item_progresso.emit(num, 100)
            self._marcar(num, titulo, caminho, "Concluído")
            return "Concluído"
        try:
            self._baixar_video(video, caminho, num, titulo, indice, total)
        except DownloadCancelado:
            self._cancelado = True
            return "Erro"
        except Exception as erro:
            texto = str(erro).lower()
            status = "Protegido" if any(p in texto for p in ("drm", "widevine", "protected")) else "Erro"
            self._marcar(num, titulo, caminho, status)
            print(f"Erro na Kiwify para '{titulo}': {erro}")
            return status
        self.item_progresso.emit(num, 100)
        self._marcar(num, titulo, caminho, "Concluído")
        return "Concluído"

    def _detalhe_da_aula(self, lesson_id):
        dados = self._get_json(f"{BASE}/courses/{self._course_id}/lesson/{lesson_id}")
        if isinstance(dados, dict):
            if isinstance(dados.get("lesson"), dict):
                return dados["lesson"]
            if isinstance(dados.get("data"), dict):
                return dados["data"]
            return dados
        return {}

    def _eh_video(self, endereco):
        texto = (endereco or "").strip().lower()
        if not texto or "drive.google." in texto or "docs.google." in texto:
            return False
        return texto.startswith("http") or any(
            p in texto for p in ("vimeo", "youtube", "youtu.be", ".mp4", ".m3u8", "pandavideo")
        )

    def _absoluto(self, url):
        if url.startswith("http"):
            return url
        if url.startswith("//"):
            return "https:" + url
        return "https://" + url.lstrip("/")

    def _url_do_video(self, aula):
        youtube = aula.get("youtube_video") or ""
        if isinstance(youtube, str) and self._eh_video(youtube):
            if "youtu" in youtube.lower():
                return self._absoluto(youtube)
        video = aula.get("video")
        if isinstance(video, dict):
            for chave in ("stream_link", "url", "hls_url", "dash_url", "source", "player_url"):
                valor = video.get(chave) or ""
                if isinstance(valor, str) and self._eh_video(valor):
                    return self._absoluto(valor)
            for chave in ("vimeo_id", "external_id"):
                ident = str(video.get(chave) or "")
                if ident.isdigit():
                    return f"https://player.vimeo.com/video/{ident}"
        elif isinstance(video, str) and self._eh_video(video):
            return self._absoluto(video)
        for chave in ("video_url", "media_url", "stream_url", "hls_url", "player_url", "embed_url", "video_link"):
            valor = aula.get(chave) or ""
            if isinstance(valor, str) and self._eh_video(valor):
                return self._absoluto(valor)
        vimeo = str(aula.get("vimeo_id") or "")
        if vimeo.isdigit():
            return f"https://player.vimeo.com/video/{vimeo}"
        conteudo = aula.get("content") if isinstance(aula.get("content"), str) else ""
        for origem in re.findall(r"""src=["']([^"']+)["']""", conteudo, re.I):
            if not self._eh_video(origem):
                continue
            if "vimeo.com/" in origem and "player.vimeo.com" not in origem:
                ident = origem.split("vimeo.com/")[-1].split("?")[0].strip("/")
                if ident:
                    return f"https://player.vimeo.com/video/{ident}"
            return origem
        return ""

    def _anexos(self, aula, pasta, forcar=False):
        if not forcar and not self.opcoes.get("baixar_anexos"):
            return []
        salvos = []
        for arquivo in self._arquivos_de(aula):
            caminho = self._baixar_arquivo(arquivo, pasta)
            if caminho:
                salvos.append(caminho)
        return salvos

    def _arquivos_de(self, aula):
        arquivos = []
        for campo in (
            "files", "attachments", "downloads", "materials", "resources",
            "complementary_materials", "downloadable_files",
        ):
            for item in aula.get(campo) or []:
                if isinstance(item, dict):
                    arquivos.append(item)
        for campo in ("file", "pdf", "document"):
            item = aula.get(campo)
            if isinstance(item, dict):
                arquivos.append(item)
        return arquivos

    def _baixar_arquivo(self, arquivo, pasta):
        nome = limpar_nome(arquivo.get("name") or arquivo.get("file_name") or arquivo.get("filename") or "anexo")
        ident = str(arquivo.get("id") or "")
        url = arquivo.get("url") if isinstance(arquivo.get("url"), str) else ""
        destino = os.path.join(pasta, nome)
        if os.path.exists(destino) and os.path.getsize(destino) > 0:
            return destino
        if ident:
            try:
                resposta = self._sessao.get(
                    f"{BASE}/courses/{self._course_id}/files/{ident}",
                    params={"forceDownload": "true"},
                    timeout=60,
                    allow_redirects=False,
                )
            except requests.RequestException:
                resposta = None
            if resposta is not None:
                if resposta.is_redirect:
                    url = resposta.headers.get("Location") or url
                elif resposta.status_code == 200 and "json" in (resposta.headers.get("Content-Type") or ""):
                    try:
                        url = (resposta.json() or {}).get("url") or url
                    except ValueError:
                        pass
                elif resposta.status_code == 200 and len(resposta.content) > 100:
                    with open(destino, "wb") as saida:
                        saida.write(resposta.content)
                    return destino
        if not url or "drive.google." in url.lower() or "docs.google." in url.lower():
            return ""
        try:
            resposta = requests.get(
                url,
                headers={"User-Agent": UA, "Referer": "https://dashboard.kiwify.com.br/"},
                timeout=60,
            )
        except requests.RequestException as erro:
            print(f"Anexo '{nome}' não baixou: {erro}")
            return ""
        if resposta.status_code != 200 or "json" in (resposta.headers.get("Content-Type") or ""):
            return ""
        if not os.path.splitext(nome)[1]:
            tipo = (resposta.headers.get("Content-Type") or "").lower()
            if "pdf" in tipo:
                destino += ".pdf"
        with open(destino, "wb") as saida:
            saida.write(resposta.content)
        return destino

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

        cabecalhos = {
            "User-Agent": UA,
            "Referer": "https://dashboard.kiwify.com.br/",
        }
        if "kiwify.com" in url.lower():
            cabecalhos["Authorization"] = f"Bearer {self._token}"
        raiz, _ext = os.path.splitext(caminho)
        opcoes = {
            "outtmpl": raiz + ".%(ext)s",
            "quiet": True,
            "no_warnings": True,
            "retries": 2,
            "fragment_retries": 2,
            "http_headers": cabecalhos,
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
