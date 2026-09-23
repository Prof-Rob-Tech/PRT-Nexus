import os
import re
import threading
import time
from pathlib import Path

from PySide6.QtCore import QMutex, QThread, QWaitCondition, Signal

EXT_VIDEO = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".wmv", ".mpg", ".mpeg"}
EXT_DOCUMENTO = {
    ".pdf", ".zip", ".rar", ".7z", ".doc", ".docx", ".xls", ".xlsx",
    ".ppt", ".pptx", ".txt", ".epub", ".csv",
}


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
    return re.sub(r"\s+", " ", texto_limpo).strip() or "arquivo"


def aceita_midia(nome, midias):
    texto = (midias or "").lower()
    ext = Path(nome).suffix.lower()
    if "video" in texto or "vídeo" in texto:
        return ext in EXT_VIDEO
    if "documento" in texto:
        return ext in EXT_DOCUMENTO
    return True


def _eh_pasta(url):
    return "/folders/" in url or "/folderview" in url


class DriveWorker(QThread):
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
        self._cancel_event = threading.Event()
        self._atual = {}
        self._ultimo_bytes = 0
        self._ultimo_tempo = 0.0

    def run(self):
        try:
            import gdown
        except ImportError:
            self.concluido.emit(False, "Instale a biblioteca do Drive: pip install gdown")
            return

        if not self.urls:
            self.concluido.emit(False, "Cole pelo menos um link público do Drive.")
            return

        nome_digitado = (self.opcoes.get("nome_conteudo") or "").strip()
        nome_raiz = nome_digitado if len(self.urls) == 1 else ""
        achatar = "Mesma Pasta" in (self.opcoes.get("estrutura") or "")
        midias = self.opcoes.get("midias") or ""
        os.makedirs(self.destino, exist_ok=True)

        try:
            itens = []
            falhas = []
            for indice, url in enumerate(self.urls, 1):
                self.progresso.emit(f"Lendo link {indice}/{len(self.urls)}...", 2)
                try:
                    itens.extend(self._itens_do_link(gdown, url, nome_raiz, achatar, midias))
                except Exception as erro:
                    falhas.append(f"{url} ({erro})")

            if not itens:
                detalhe = ""
                if falhas:
                    detalhe = " Confira se o link é público. " + " | ".join(falhas[:2])
                self.concluido.emit(False, "Nenhum arquivo encontrado para o filtro escolhido." + detalhe)
                return

            self._evitar_nomes_repetidos(itens)
            erros = len(falhas)

            for idx, item in enumerate(itens, 1):
                self._checar_pausa()
                if self._cancelado:
                    break

                destino = Path(self.destino).joinpath(*item["partes"])
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
                    self.progresso.emit(
                        f"Já existe ({idx}/{len(itens)}): {item['titulo'][:40]}",
                        min(int(idx / len(itens) * 100), 99),
                    )
                    continue

                self._atual = {"idx": idx, "total": len(itens), "num": num, "nome": item["titulo"]}
                self._ultimo_bytes = 0
                self._ultimo_tempo = time.time()
                try:
                    destino.parent.mkdir(parents=True, exist_ok=True)
                    gdown.download(
                        id=item["id"],
                        output=str(destino),
                        quiet=True,
                        resume=True,
                        use_cookies=False,
                        progress=self._ao_progresso,
                        cancel=self._cancel_event,
                    )
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
                    if self._cancelado or self._cancel_event.is_set():
                        self._cancelado = True
                        break
                    erros += 1
                    self.item_concluido.emit({
                        "num": num,
                        "titulo": item["titulo"],
                        "caminho": str(destino),
                        "status": "Erro",
                    })
                    print(f"Erro no Drive para '{item['titulo']}': {erro}")

            if self._cancelado:
                self.velocidade.emit("-- MiB/s | ETA: --:--")
                return

            self.velocidade.emit("-- MiB/s | ETA: --:--")
            self.progresso.emit("Processo concluído!", 100)
            if erros:
                self.concluido.emit(False, f"Fila concluída com {erros} falha(s).")
            else:
                self.concluido.emit(True, f"Fila concluída: {len(itens)} arquivo(s) de {len(self.urls)} link(s).")
        except Exception as erro:
            self.concluido.emit(False, f"Erro no conector do Drive: {erro}")

    def _itens_do_link(self, gdown, url, nome_raiz, achatar, midias):
        if _eh_pasta(url):
            lista = gdown.download_folder(
                url=url,
                output=self.destino,
                quiet=True,
                skip_download=True,
                use_cookies=False,
            )
            itens = []
            for arquivo in lista or []:
                relativo = (arquivo.path or "").replace("\\", "/")
                partes = [limpar_segmento(p) for p in relativo.split("/") if p]
                if not partes:
                    continue
                if nome_raiz:
                    partes[0] = limpar_segmento(nome_raiz)
                if achatar:
                    topo = partes[0] if len(partes) > 1 else (nome_raiz or "Drive")
                    partes = [topo, partes[-1]]
                if not aceita_midia(partes[-1], midias):
                    continue
                itens.append({"id": arquivo.id, "titulo": partes[-1], "partes": partes})
            return itens

        info = gdown.download(url=url, quiet=True, skip_download=True, use_cookies=False)
        nome = limpar_segmento(Path(getattr(info, "path", "") or "arquivo").name)
        if not aceita_midia(nome, midias):
            return []
        pasta = limpar_segmento(nome_raiz) if nome_raiz else "Drive"
        return [{"id": info.id, "titulo": nome, "partes": [pasta, nome]}]

    def _evitar_nomes_repetidos(self, itens):
        usados = set()
        for item in itens:
            pasta = item["partes"][:-1]
            arquivo = item["partes"][-1]
            base, ext = os.path.splitext(arquivo)
            candidato = arquivo
            indice = 2
            while "/".join([*pasta, candidato]).lower() in usados:
                candidato = f"{base}_{indice}{ext}"
                indice += 1
            item["partes"] = [*pasta, candidato]
            item["titulo"] = candidato
            usados.add("/".join(item["partes"]).lower())

    def _ao_progresso(self, feito, total):
        self._checar_pausa()
        if self._cancelado:
            self._cancel_event.set()
            raise DownloadCancelado()
        atual = self._atual
        if not atual:
            return
        agora = time.time()
        if agora - self._ultimo_tempo >= 0.3:
            self._emitir_velocidade(feito - self._ultimo_bytes, agora - self._ultimo_tempo, (total or feito) - feito)
            self._ultimo_tempo = agora
            self._ultimo_bytes = feito
        pct = int(feito / total * 100) if total else 0
        self.item_progresso.emit(atual["num"], min(pct, 99))
        self.progresso.emit(
            f"Baixando ({atual['idx']}/{atual['total']}): {atual['nome'][:40]}",
            min(max(int(((atual["idx"] - 1) + pct / 100) / atual["total"] * 100), 1), 99),
        )

    def _emitir_velocidade(self, bytes_delta, segundos, restante):
        if segundos <= 0 or bytes_delta < 0:
            return
        taxa = bytes_delta / segundos
        mib = taxa / (1024 * 1024)
        eta = int(restante / taxa) if taxa else 0
        horas, resto = divmod(max(eta, 0), 3600)
        minutos, segs = divmod(resto, 60)
        texto_eta = f"{horas:02d}:{minutos:02d}:{segs:02d}" if horas else f"{minutos:02d}:{segs:02d}"
        self.velocidade.emit(f"{mib:.2f}MiB/s | ETA: {texto_eta}")

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
        self._cancel_event.set()
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
