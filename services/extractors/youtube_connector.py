import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QMutex, QThread, QWaitCondition, Signal


class DownloadCancelado(Exception):
    pass


def separar_links(texto):
    """Um link por linha. Linhas vazias e repetidas saem da fila."""
    links = []
    vistos = set()
    for parte in re.split(r"[\s,;]+", texto or ""):
        link = parte.strip()
        if not link:
            continue
        if not link.startswith("http"):
            link = "https://" + link.lstrip("/")
        chave = link.lower()
        if chave in vistos:
            continue
        vistos.add(chave)
        links.append(link)
    return links


def limpar_segmento(texto):
    texto_limpo = re.sub(r'[\\/*?:"<>|]', "", texto or "")
    return re.sub(r"\s+", " ", texto_limpo).strip() or "video"


def argumentos_qualidade(qualidade):
    texto = qualidade or ""
    if "MP3" in texto or "Áudio" in texto or "Audio" in texto:
        return ["-x", "--audio-format", "mp3", "--audio-quality", "192", "-f", "ba/b"], "mp3"
    if "1080" in texto:
        formato = "bv*[height<=1080]+ba/b[height<=1080]/best[height<=1080]/b"
    elif "720" in texto:
        formato = "bv*[height<=720]+ba/b[height<=720]/best[height<=720]/b"
    else:
        formato = "bv*+ba/b"
    return ["-f", formato, "--merge-output-format", "mp4"], "mp4"


def eh_video_unico(url):
    """watch, youtu.be e shorts são um vídeo, mesmo quando o YouTube cola &list=."""
    texto = url or ""
    if re.search(r"youtu\.be/[\w-]+", texto, re.I):
        return True
    if re.search(r"youtube\.com/(?:shorts|embed|live|v)/[\w-]+", texto, re.I):
        return True
    return bool(re.search(r"[?&]v=[\w-]+", texto, re.I))


def url_de_videos_do_canal(url):
    """Canal, @usuario e /channel viram a aba Vídeos, com todos os vídeos públicos."""
    if eh_video_unico(url):
        return ""
    sem_query = (url or "").split("#")[0].split("?")[0].rstrip("/")
    match = re.search(
        r"(https?://(?:www\.)?youtube\.com/(?:@[\w.\-]+|channel/UC[\w-]+|c/[\w.\-]+|user/[\w.\-]+))(?:/(videos|shorts|streams|playlists|featured))?$",
        sem_query,
        re.I,
    )
    if not match:
        return ""
    aba = (match.group(2) or "").lower()
    if aba in ("shorts", "streams", "playlists"):
        return sem_query
    return match.group(1) + "/videos"


def nome_do_canal(dados):
    for chave in ("channel", "uploader", "playlist_channel"):
        nome = limpar_segmento(dados.get(chave) or "")
        if nome and nome.lower() not in ("videos", "vídeos", "shorts"):
            return nome
    titulo = re.sub(r"\s*-\s*videos$", "", dados.get("title") or dados.get("playlist_title") or "", flags=re.I)
    return limpar_segmento(titulo) or "Canal"


def ffmpeg_disponivel():
    achado = shutil.which("ffmpeg")
    if achado:
        return achado
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return ""


def mensagem_acesso(texto):
    baixo = (texto or "").lower()
    if any(p in baixo for p in ("private", "members-only", "members only", "sign in", "login", "cookies", "confirm your age", "age-restricted", "age restricted")):
        return "Esse conteúdo não é público. Vídeo privado, só para membros ou com restrição de idade fica de fora."
    return (texto or "não foi possível ler o link").strip()


class YouTubeWorker(QThread):
    progresso = Signal(str, int)
    velocidade = Signal(str)
    item_progresso = Signal(str, int)
    item_concluido = Signal(dict)
    concluido = Signal(bool, str)

    def __init__(self, url, destino, opcoes=None, parent=None, urls=None):
        super().__init__(parent)
        if urls is None:
            self.urls = separar_links(url or "")
        else:
            self.urls = [item for item in urls if (item or "").strip()]
        self.destino = (destino or "").strip() or os.path.join(os.path.expanduser("~"), "Downloads", "PRT_Nexus")
        self.opcoes = opcoes or {}
        self._pausado = False
        self._cancelado = False
        self._mutex = QMutex()
        self._condicao = QWaitCondition()
        self._processo = None

    def run(self):
        if not self.urls:
            self.concluido.emit(False, "Cole pelo menos um link do YouTube.")
            return

        flags, extensao = argumentos_qualidade(self.opcoes.get("qualidade") or "")
        os.makedirs(os.path.join(self.destino, self._pasta_base()), exist_ok=True)

        try:
            itens = []
            falhas = []
            for indice, url in enumerate(self.urls, 1):
                self._checar_pausa()
                if self._cancelado:
                    break
                if self.opcoes.get("canal"):
                    self.progresso.emit(f"Lendo as aulas do canal ({indice}/{len(self.urls)})...", 2)
                else:
                    self.progresso.emit(f"Lendo link {indice}/{len(self.urls)}...", 2)
                try:
                    itens.extend(self._itens_do_link(url, extensao))
                except Exception as erro:
                    falhas.append(mensagem_acesso(str(erro)))

            if self._cancelado:
                self.velocidade.emit("-- MiB/s | ETA: --:--")
                return

            if not itens:
                detalhe = f" {falhas[0]}" if falhas else ""
                self.concluido.emit(False, "Nenhum vídeo público encontrado nesse link." + detalhe)
                return

            self._evitar_nomes_repetidos(itens)
            erros = len(falhas)
            for idx, item in enumerate(itens, 1):
                self._checar_pausa()
                if self._cancelado:
                    break
                destino = Path(item["caminho"])
                num = str(idx)
                self.item_concluido.emit({
                    "num": num,
                    "titulo": item["titulo"],
                    "caminho": str(destino),
                    "status": "Na fila",
                })
                if destino.exists() and destino.stat().st_size > 0:
                    self.item_progresso.emit(num, 100)
                    self.item_concluido.emit({
                        "num": num,
                        "titulo": item["titulo"],
                        "caminho": str(destino),
                        "status": "Concluído",
                    })
                    continue
                try:
                    self._baixar(item["url"], destino, flags, idx, len(itens), num, item["titulo"])
                    self.item_progresso.emit(num, 100)
                    self.item_concluido.emit({
                        "num": num,
                        "titulo": item["titulo"],
                        "caminho": str(destino),
                        "status": "Concluído",
                    })
                except DownloadCancelado:
                    self._cancelado = True
                    break
                except Exception as erro:
                    erros += 1
                    self.item_concluido.emit({
                        "num": num,
                        "titulo": item["titulo"],
                        "caminho": str(destino),
                        "status": "Erro",
                    })
                    print(f"Erro no YouTube para '{item['titulo']}': {mensagem_acesso(str(erro))}")

            if self._cancelado:
                self.velocidade.emit("-- MiB/s | ETA: --:--")
                return

            self.velocidade.emit("-- MiB/s | ETA: --:--")
            self.progresso.emit("Processo concluído!", 100)
            if erros:
                self.concluido.emit(False, f"Fila concluída com {erros} falha(s).")
            else:
                self.concluido.emit(True, f"Fila concluída: {len(itens)} vídeo(s) de {len(self.urls)} link(s).")
        except Exception as erro:
            self.concluido.emit(False, f"Erro no conector do YouTube: {erro}")

    def _pasta_base(self):
        nome = (self.opcoes.get("pasta_videos") or "").strip()
        return limpar_segmento(nome) if nome else "Youtube"

    def _pasta_do_canal(self, dados):
        nome = (self.opcoes.get("pasta_canal") or "").strip()
        return limpar_segmento(nome) if nome else nome_do_canal(dados)

    def _itens_do_link(self, url, extensao):
        canal = bool(self.opcoes.get("canal"))
        endereco_canal = url_de_videos_do_canal(url)
        if canal and not endereco_canal:
            raise RuntimeError("Cole o link do canal, como youtube.com/@canal.")
        if not canal and endereco_canal:
            raise RuntimeError("Link de canal entra em Baixar aulas do canal.")
        endereco = endereco_canal or url
        comando = [sys.executable, "-m", "yt_dlp", "-J", "--no-warnings", "--no-colors"]
        comando.append("--no-playlist" if eh_video_unico(url) else "--flat-playlist")
        comando.append(endereco)
        resultado = subprocess.run(comando, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if resultado.returncode != 0 or not (resultado.stdout or "").strip():
            detalhe = (resultado.stderr or resultado.stdout or "não foi possível ler o link").strip().splitlines()
            raise RuntimeError(detalhe[-1][:180] if detalhe else "não foi possível ler o link")
        dados = json.loads(resultado.stdout)
        entradas = dados.get("entries") or [dados]
        if canal:
            pasta = os.path.join(self.destino, self._pasta_base(), self._pasta_do_canal(dados))
        else:
            pasta = os.path.join(self.destino, self._pasta_base())
        itens = []
        for ordem, entrada in enumerate(entradas, 1):
            if not entrada:
                continue
            titulo = limpar_segmento(entrada.get("title") or entrada.get("id") or "video")
            video = self._endereco_da_entrada(entrada)
            if not video:
                continue
            if dados.get("entries"):
                numero = entrada.get("playlist_index") or ordem
                try:
                    numero = int(numero)
                except (TypeError, ValueError):
                    numero = ordem
                nome_arquivo = f"{numero:02d} - {titulo}"
            else:
                nome_arquivo = titulo
            caminho = os.path.join(pasta, f"{nome_arquivo}.{extensao}")
            itens.append({"titulo": nome_arquivo, "url": video, "caminho": caminho})
        return itens

    def _endereco_da_entrada(self, entrada):
        for chave in ("webpage_url", "original_url", "url"):
            endereco = str(entrada.get(chave) or "")
            if re.search(r"(?:watch\?v=|youtu\.be/|shorts/)", endereco, re.I):
                return endereco
        ident = str(entrada.get("id") or entrada.get("url") or "")
        if re.fullmatch(r"[\w-]{11}", ident):
            return f"https://www.youtube.com/watch?v={ident}"
        return ""

    def _evitar_nomes_repetidos(self, itens):
        usados = set()
        for item in itens:
            caminho = item["caminho"]
            pasta, arquivo = os.path.split(caminho)
            base, ext = os.path.splitext(arquivo)
            candidato = arquivo
            indice = 2
            while os.path.join(pasta, candidato).lower() in usados:
                candidato = f"{base}_{indice}{ext}"
                indice += 1
            item["caminho"] = os.path.join(pasta, candidato)
            item["titulo"] = os.path.splitext(candidato)[0]
            usados.add(item["caminho"].lower())

    def _baixar(self, url, destino, flags, idx, total, num, titulo):
        destino.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg = ffmpeg_disponivel()
        if not ffmpeg:
            raise RuntimeError("Instale o ffmpeg para juntar o vídeo e o áudio do YouTube.")
        comando = [
            sys.executable, "-m", "yt_dlp",
            "--newline",
            "--no-colors",
            "--no-playlist",
            "--progress",
            "--ffmpeg-location", ffmpeg,
            *flags,
            "-o", str(destino),
            "--referer", "https://www.youtube.com/",
            url,
        ]
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        processo = subprocess.Popen(
            comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            bufsize=1,
        )
        self._processo = processo
        if self._pausado:
            self._suspender_processo(True)
        try:
            if processo.stdout:
                for linha in processo.stdout:
                    if self._cancelado:
                        processo.kill()
                        raise DownloadCancelado()
                    self._checar_pausa()
                    texto = linha.strip()
                    match = re.search(r"(\d+(?:\.\d+)?)\s*%", texto)
                    if match:
                        pct = float(match.group(1))
                        self.item_progresso.emit(num, min(pct, 99))
                        global_pct = int(((idx - 1) + pct / 100) / total * 100)
                        self.progresso.emit(
                            f"Baixando ({idx}/{total}): {titulo[:40]}",
                            min(max(global_pct, 1), 99),
                        )
                    vel = re.search(r"at\s+(\S+)\s+ETA\s+(\S+)", texto)
                    if vel:
                        self.velocidade.emit(f"{vel.group(1)} | ETA: {vel.group(2)}")
            processo.wait()
        finally:
            self._processo = None
        if self._cancelado:
            raise DownloadCancelado()
        if processo.returncode != 0 or not destino.exists():
            raise RuntimeError(mensagem_acesso(f"yt-dlp saiu com código {processo.returncode}"))

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
        self._cancelado = True
        processo = self._processo
        if processo and processo.poll() is None:
            self._suspender_processo(False)
            processo.kill()
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
