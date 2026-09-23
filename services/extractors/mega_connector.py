import os
import re
import time
from pathlib import Path

from PySide6.QtCore import QMutex, QThread, QWaitCondition, Signal

EXT_VIDEO = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".wmv", ".mpg", ".mpeg"}
EXT_DOCUMENTO = {
    ".pdf", ".zip", ".rar", ".7z", ".doc", ".docx", ".xls", ".xlsx",
    ".ppt", ".pptx", ".txt", ".epub", ".csv",
}
CHUNK = 1024 * 1024


class DownloadCancelado(Exception):
    pass


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


def _partes_do_no(nodes, node):
    por_handle = {item.handle: item for item in nodes}
    nomes = [node.name]
    atual = por_handle.get(node.parent or "")
    vistos = set()
    while atual is not None and atual.handle not in vistos:
        vistos.add(atual.handle)
        if atual.name:
            nomes.append(atual.name)
        atual = por_handle.get(atual.parent or "")
    return [limpar_segmento(nome) for nome in reversed(nomes)]


def listar_arquivos(nodes, nome_raiz, achatar, midias, somente_handle=None):
    """Monta o caminho local de cada arquivo da pasta do Mega."""
    raiz = limpar_segmento(nome_raiz) if (nome_raiz or "").strip() else ""
    usados = set()
    itens = []

    for node in nodes:
        if not getattr(node, "is_file", False):
            continue
        if somente_handle and node.handle != somente_handle:
            continue
        chave = getattr(node, "key", None)
        if chave is not None and not hasattr(chave, "meta_mac"):
            continue
        if node.size is None:
            continue
        if not aceita_midia(node.name, midias):
            continue

        partes = _partes_do_no(nodes, node)
        if not partes:
            continue
        if raiz:
            partes[0] = raiz
        if achatar:
            pasta = raiz or partes[0]
            arquivo = partes[-1]
            base, ext = os.path.splitext(arquivo)
            candidato = arquivo
            indice = 2
            while f"{pasta}/{candidato}".lower() in usados:
                candidato = f"{base}_{indice}{ext}"
                indice += 1
            partes = [pasta, candidato]

        relativo = "/".join(partes)
        if relativo.lower() in usados:
            continue
        usados.add(relativo.lower())
        itens.append({
            "titulo": partes[-1],
            "partes": partes,
            "size": int(node.size or 0),
            "node": node,
        })
    return itens


class MegaWorker(QThread):
    progresso = Signal(str, int)
    velocidade = Signal(str)
    item_progresso = Signal(str, int)
    item_concluido = Signal(dict)
    concluido = Signal(bool, str)

    def __init__(self, url, destino, opcoes=None, parent=None):
        super().__init__(parent)
        self.url = (url or "").strip()
        self.destino = (destino or "").strip() or os.path.join(os.path.expanduser("~"), "Downloads", "PRT_Nexus")
        self.opcoes = opcoes or {}
        self._pausado = False
        self._cancelado = False
        self._mutex = QMutex()
        self._condicao = QWaitCondition()

    def run(self):
        try:
            from mega_client import FileInfo, MegaClient, MegaClientError, MegaInvalidURLError, parse_mega_url
            from mega_client.downloader import Downloader
        except ImportError:
            self.concluido.emit(False, "Instale a biblioteca do Mega: pip install mega-public-client")
            return

        if not self.url.startswith("http"):
            self.url = "https://" + self.url.lstrip("/")

        try:
            link = parse_mega_url(self.url)
        except MegaInvalidURLError:
            self.concluido.emit(
                False,
                "Link do Mega inválido. Use um link público de arquivo ou de pasta.",
            )
            return

        nome_raiz = (self.opcoes.get("nome_conteudo") or "").strip()
        achatar = "Mesma Pasta" in (self.opcoes.get("estrutura") or "")
        midias = self.opcoes.get("midias") or ""
        os.makedirs(self.destino, exist_ok=True)

        try:
            with MegaClient() as client:
                self.progresso.emit("Lendo o link do Mega...", 5)
                if link.type.value == "file":
                    info = client.get_file_info(self.url)
                    pasta = limpar_segmento(nome_raiz) if nome_raiz else "Mega"
                    itens = [{
                        "titulo": limpar_segmento(info.name),
                        "partes": [pasta, limpar_segmento(info.name)],
                        "size": int(info.size or 0),
                        "info": info,
                        "node": None,
                    }]
                    if not aceita_midia(info.name, midias):
                        itens = []
                else:
                    pasta = client.get_folder_info(self.url)
                    itens = listar_arquivos(
                        pasta.nodes,
                        nome_raiz,
                        achatar,
                        midias,
                        somente_handle=link.selected_file,
                    )
                    for item in itens:
                        item["info"] = None

                if not itens:
                    self.concluido.emit(False, "Nenhum arquivo encontrado para o filtro escolhido.")
                    return

                total_bytes = sum(item["size"] for item in itens) or 1
                bytes_feitos = 0
                erros = 0
                baixador = Downloader(client._client, client.retry, parallelism=1)

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

                    if destino.exists() and destino.stat().st_size == item["size"] and item["size"] > 0:
                        bytes_feitos += item["size"]
                        self.item_progresso.emit(num, 100)
                        self.item_concluido.emit({
                            "num": num,
                            "titulo": item["titulo"],
                            "caminho": str(destino),
                            "status": "Concluído",
                        })
                        self.progresso.emit(
                            f"Já existe ({idx}/{len(itens)}): {item['titulo'][:40]}",
                            min(int(bytes_feitos / total_bytes * 100), 99),
                        )
                        continue

                    try:
                        info = item["info"]
                        if info is None:
                            node = item["node"]
                            info = FileInfo(
                                name=node.name,
                                size=node.size,
                                download_url=client._node_download_url(pasta.handle, node.handle),
                                key=node.key,
                                handle=node.handle,
                                attributes=node.attributes,
                            )
                        self._baixar_arquivo(baixador, info, destino, idx, len(itens), bytes_feitos, total_bytes, num)
                        bytes_feitos += item["size"]
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
                    except (MegaClientError, OSError) as erro:
                        erros += 1
                        self.item_concluido.emit({
                            "num": num,
                            "titulo": item["titulo"],
                            "caminho": str(destino),
                            "status": "Erro",
                        })
                        print(f"Erro no Mega para '{item['titulo']}': {erro}")

                if self._cancelado:
                    self.velocidade.emit("-- MiB/s | ETA: --:--")
                    return

                self.velocidade.emit("-- MiB/s | ETA: --:--")
                self.progresso.emit("Processo concluído!", 100)
                if erros:
                    self.concluido.emit(False, f"Concluído com {erros} arquivo(s) que falharam.")
                else:
                    self.concluido.emit(True, "Arquivos do Mega salvos.")
        except MegaClientError as erro:
            self.concluido.emit(False, f"Erro no Mega: {erro}")
        except Exception as erro:
            self.concluido.emit(False, f"Erro no conector do Mega: {erro}")

    def _baixar_arquivo(self, baixador, info, destino, idx, total, bytes_feitos, total_bytes, num):
        from mega_client.crypto import iter_mega_chunks
        from mega_client.utils import ensure_directory

        ensure_directory(destino.parent)
        temporario = destino.with_suffix(destino.suffix + ".part")
        existente = temporario.stat().st_size if temporario.exists() else 0
        if existente % 16:
            existente -= existente % 16
            with temporario.open("r+b") as arquivo:
                arquivo.truncate(existente)
        if not temporario.exists():
            temporario.touch()

        feito = existente
        ultimo_tempo = time.time()
        ultimo_feito = feito
        faixas = [
            (max(inicio, existente), fim)
            for inicio, fim in iter_mega_chunks(info.size, CHUNK)
            if fim > existente
        ]
        for inicio, fim in faixas:
            self._checar_pausa()
            if self._cancelado:
                raise DownloadCancelado()
            pedaco = baixador._fetch_decrypted_range(info, inicio, fim)
            with temporario.open("r+b") as arquivo:
                arquivo.seek(inicio)
                arquivo.write(pedaco)
            feito += len(pedaco)
            agora = time.time()
            if agora - ultimo_tempo >= 0.3:
                self._emitir_velocidade(feito - ultimo_feito, agora - ultimo_tempo, info.size - feito)
                ultimo_tempo = agora
                ultimo_feito = feito
            pct_arquivo = int(feito / info.size * 100) if info.size else 100
            self.item_progresso.emit(num, min(pct_arquivo, 99))
            pct_global = int((bytes_feitos + feito) / total_bytes * 100)
            self.progresso.emit(
                f"Baixando ({idx}/{total}): {info.name[:40]}",
                min(max(pct_global, 1), 99),
            )

        if temporario.stat().st_size != info.size:
            raise OSError(f"Download incompleto: {temporario.stat().st_size}/{info.size}")
        temporario.replace(destino)

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
