import os
import re
import requests
import time
from PySide6.QtCore import QThread, Signal, QMutex, QWaitCondition
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

try:
    from services.extractors.chip7_mapper import Chip7Mapper
except ImportError:
    from services.chip7_mapper import Chip7Mapper


class DownloadCancelado(Exception):
    pass


class Chip7Worker(QThread):
    progresso = Signal(str, int)
    velocidade = Signal(str)
    item_progresso = Signal(str, int)
    item_concluido = Signal(dict)
    concluido = Signal(bool, str)

    NOMES_GENERICOS = [
        "CHIP 7 - CURSO EXTRAÍDO",
        "CHIP 7 - CURSO EXTRAIDO",
        "01 - CHIP 7 - CURSO EXTRAÍDO",
        "CHIP 7 CONTEUDO",
        "CHIP 7 CONTEÚDO",
        "SEM_NOME"
    ]

    def __init__(self, url, email, senha, destino, modo_avulso=False, opcoes=None, parent=None):
        super().__init__(parent)
        self._pausado = False
        self._mutex = QMutex()
        self._condicao = QWaitCondition()
        
        self.url = url.strip() if url else ""
        self.email = email.strip() if email else ""
        self.senha = senha.strip() if senha else ""
        self.destino = destino.strip() if destino else os.path.join(os.path.expanduser("~"), "Downloads", "PRT_Nexus")
        self.modo_avulso = modo_avulso
        self.opcoes = opcoes or {}
        self.relatorio_txt = []
        self._cancelado = False
        self._video_avulso = ""

    def extrair_url_video(self, driver):
        """Busca URLs de player em iframes, tags video ou scripts da página."""
        if self.modo_avulso and self._video_avulso:
            return self._video_avulso

        time.sleep(2.5)
        video_url = None

        # 1. Procura em iFrames
        try:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for iframe in iframes:
                src = iframe.get_attribute("src") or iframe.get_attribute("data-src") or ""
                if src and any(p in src.lower() for p in ["vimeo", "youtube", "panda", "wistia", "player", "embed", "converteai", "vturb", "bunny"]):
                    video_url = src
                    break
        except Exception:
            pass

        # 2. Procura em tags <video> ou <source>
        if not video_url:
            try:
                videos = driver.find_elements(By.TAG_NAME, "video")
                for v in videos:
                    src = v.get_attribute("src")
                    if src and not src.startswith("blob:"):
                        video_url = src
                        break
                    
                    sources = v.find_elements(By.TAG_NAME, "source")
                    for s in sources:
                        s_src = s.get_attribute("src")
                        if s_src:
                            video_url = s_src
                            break
                    if video_url:
                        break
            except Exception:
                pass

        # 3. Varredura em scripts da página para links HLS (.m3u8)
        if not video_url:
            try:
                page_source = driver.page_source
                m3u8_matches = re.findall(r'https?://[^\s\'"]+\.m3u8[^\s\'"]*', page_source)
                if m3u8_matches:
                    video_url = m3u8_matches[0]
            except Exception:
                pass

        return video_url

    def _baixar_anexos_aula(self, driver, pasta_destino):
        """Localiza e descarrega arquivos anexos da página da aula."""
        if not self.opcoes.get("baixar_anexos", False):
            return

        try:
            links = driver.find_elements(By.TAG_NAME, "a")
            extensoes_validas = ('.pdf', '.zip', '.rar', '.7z', '.epub', '.docx', '.xlsx', '.pptx', '.txt')
            headers = {'User-Agent': driver.execute_script("return navigator.userAgent;")}

            for link in links:
                self._checar_pausa()
                try:
                    href = link.get_attribute("href")
                    if not href or href.startswith("javascript:"):
                        continue
                    
                    nome_link = link.text.strip() or "anexo"
                    is_anexo = any(href.lower().endswith(ext) or ext in href.lower() for ext in extensoes_validas)
                    
                    if is_anexo or "download" in href.lower() or "attachment" in href.lower():
                        nome_limpo = re.sub(r'[\\/*?:"<>|]', '_', nome_link)
                        if not any(nome_limpo.lower().endswith(ext) for ext in extensoes_validas):
                            match_ext = re.search(r'\.(pdf|zip|rar|7z|epub|docx|xlsx|pptx|txt)', href, re.IGNORECASE)
                            ext = match_ext.group(0) if match_ext else ".pdf"
                            nome_limpo += ext

                        caminho_anexo = os.path.join(pasta_destino, nome_limpo)
                        if not os.path.exists(caminho_anexo):
                            resp = requests.get(href, headers=headers, timeout=15)
                            if resp.status_code == 200:
                                with open(caminho_anexo, "wb") as f:
                                    f.write(resp.content)
                except Exception:
                    continue
        except Exception:
            pass

    def _coletar_descricao_aula(self, driver, num_mod, titulo_mod, num_aula, titulo_aula):
        """Coleta descrições para o arquivo de texto."""
        if not self.opcoes.get("gerar_txt", False):
            return

        texto_descricao = ""
        try:
            elementos_texto = driver.find_elements(
                By.XPATH, 
                "//div[contains(@class, 'desc') or contains(@class, 'content') or contains(@class, 'text') or contains(@class, 'lesson')]//p"
            )
            if elementos_texto:
                paragrafos = [el.text.strip() for el in elementos_texto if el.text.strip()]
                texto_descricao = "\n".join(paragrafos)
        except Exception:
            pass

        if not texto_descricao:
            texto_descricao = "Sem descrição de texto disponível para esta aula."

        bloco = (
            f"MÓDULO {num_mod:02d}: {titulo_mod}\n"
            f"AULA {num_aula:02d}: {titulo_aula}\n"
            f"LINK: {driver.current_url}\n"
            f"DESCRIÇÃO:\n{texto_descricao}\n"
            f"{'-'*60}\n\n"
        )
        self.relatorio_txt.append(bloco)

    def _id_do_curso(self):
        match = re.search(r"/curso/(\d+)", self.url)
        return match.group(1) if match else ""

    def _src_do_path(self, path):
        if not path:
            return ""
        texto = str(path).replace("&amp;", "&")
        match = re.search(r"""<iframe\s[^>]*src=["']([^"']+)["']""", texto, re.I)
        if match:
            return match.group(1)
        if texto.startswith("http"):
            return texto.strip()
        return ""

    def _combinar_aula(self, aulas, nome):
        alvo = Chip7Mapper.normalizar(nome)
        exatas = []
        parciais = []
        for aula in aulas:
            titulo = (aula.get("titulo") or "").strip()
            norm = Chip7Mapper.normalizar(titulo)
            if not norm:
                continue
            if norm == alvo:
                exatas.append(aula)
            elif alvo and norm.startswith(alvo):
                resto = norm[len(alvo):]
                if resto[:1].isdigit() and alvo[-1:].isdigit():
                    continue
                parciais.append(aula)
        if exatas:
            return exatas[0]
        if len(parciais) == 1:
            return parciais[0]
        return None

    def _aulas_do_curso(self, driver):
        course_id = self._id_do_curso()
        if not course_id:
            return []
        driver.set_script_timeout(20)
        try:
            dados = driver.execute_async_script(
                """
                const courseId = arguments[0];
                const done = arguments[arguments.length - 1];
                fetch("/api/student_lessons.php?course_id=" + encodeURIComponent(courseId), {
                    credentials: "include"
                })
                    .then((resp) => resp.json())
                    .then((json) => done(json))
                    .catch((erro) => done({ ok: false, message: String(erro) }));
                """,
                course_id,
            )
        except Exception:
            return []
        if not isinstance(dados, dict) or not dados.get("ok"):
            return []
        return dados.get("aulas") or []

    def _clicar_botao_aula(self, driver, titulo):
        alvo = Chip7Mapper.normalizar(titulo)
        if not alvo:
            return False
        try:
            return bool(driver.execute_script(
                """
                const alvo = arguments[0];
                const normalizar = (texto) => (texto || "")
                    .normalize("NFD")
                    .replace(/[\\u0300-\\u036f]/g, "")
                    .toUpperCase()
                    .replace(/[^A-Z0-9]/g, "");
                const botoes = Array.from(document.querySelectorAll("button.student-lesson-nav__btn"));
                let escolhido = botoes.find((btn) => normalizar(btn.innerText) === alvo);
                if (!escolhido) {
                    const parciais = botoes.filter((btn) => normalizar(btn.innerText).startsWith(alvo));
                    if (parciais.length === 1) escolhido = parciais[0];
                }
                if (!escolhido) return false;
                escolhido.scrollIntoView({block: "center"});
                escolhido.click();
                return true;
                """,
                alvo,
            ))
        except Exception:
            return False

    def _titulo_aula_aberta(self, driver):
        try:
            titulo = driver.execute_script(
                """
                const el = document.querySelector("h1.student-lesson-main__title");
                return el ? (el.innerText || "").replace(/\\s+/g, " ").trim() : "";
                """
            )
        except Exception:
            titulo = ""
        return (titulo or "").strip()

    def _iframe_aula_aberta(self, driver):
        try:
            src = driver.execute_script(
                """
                const el = document.querySelector("iframe.student-embed__iframe");
                return el ? (el.getAttribute("src") || "") : "";
                """
            )
        except Exception:
            src = ""
        return (src or "").strip()

    def _abrir_aula_avulsa(self, driver, mapper, nome_pedido):
        """No Chip 7 todas as aulas usam a URL do curso. A troca é o botão do menu."""
        aulas = self._aulas_do_curso(driver)
        aula = self._combinar_aula(aulas, nome_pedido)
        if not aula and not aulas:
            time.sleep(2)
            aulas = self._aulas_do_curso(driver)
            aula = self._combinar_aula(aulas, nome_pedido)
        if not aula:
            return ""

        titulo = (aula.get("titulo") or nome_pedido).strip()
        self._video_avulso = self._src_do_path(aula.get("path"))
        self._clicar_botao_aula(driver, titulo)

        alvo = Chip7Mapper.normalizar(titulo)
        for _ in range(25):
            time.sleep(0.3)
            titulo_visto = self._titulo_aula_aberta(driver)
            if Chip7Mapper.normalizar(titulo_visto) != alvo:
                continue
            iframe = self._iframe_aula_aberta(driver)
            if iframe:
                self._video_avulso = iframe
            return mapper.limpar_nome(titulo_visto) or mapper.limpar_nome(titulo)

        if self._video_avulso:
            return mapper.limpar_nome(titulo)
        return ""

    def _resolver_nome_curso(self, mapper, modulo):
        """Determina o nome da pasta do curso descartando termos genéricos."""
        nome_custom = self.opcoes.get("nome_conteudo", "").strip()
        nome_extraido = modulo.get("nome_curso", "").strip()

        if nome_custom and nome_custom.upper() not in self.NOMES_GENERICOS:
            return mapper.limpar_nome(nome_custom)

        if nome_extraido and nome_extraido.upper() not in self.NOMES_GENERICOS:
            return mapper.limpar_nome(nome_extraido)

        return "FACE ID 3.0"

    def _formato_download(self):
        """Traduz a qualidade escolhida na tela para o formato do yt-dlp."""
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
            formato = "best[ext=mp4]/b/bestvideo+bestaudio/best"
        return {
            "ext": "mp4",
            "ydl": {
                "format": formato,
                "merge_output_format": "mp4",
            },
        }

    def _destino_da_aula(self, nome_curso, num_mod, titulo_mod, num_aula, titulo_aula, indice_global):
        """Aplica estrutura e numeração escolhidas na tela."""
        estrutura = self.opcoes.get("estrutura") or ""
        midias = self.opcoes.get("midias") or ""
        por_modulo = "Mesma Pasta" not in estrutura
        sequencial = "Original" not in midias

        pasta_curso = os.path.join(self.destino, f"01 - {nome_curso}")
        pasta = os.path.join(pasta_curso, f"{num_mod:02d} - {titulo_mod}") if por_modulo else pasta_curso
        numero = num_aula if por_modulo else indice_global
        nome_arquivo = f"{numero:02d} - {titulo_aula}" if sequencial else titulo_aula
        return pasta, nome_arquivo

    def run(self):
        driver = None
        try:
            os.makedirs(self.destino, exist_ok=True)

            self.progresso.emit("A iniciar o Google Chrome...", 5)
            options = webdriver.ChromeOptions()
            options.add_argument("--start-maximized")
            options.add_argument("--disable-notifications")
            options.add_argument("--mute-audio")
            
            driver = webdriver.Chrome(options=options)
            user_agent = driver.execute_script("return navigator.userAgent;")
            
            self.progresso.emit("A aceder ao Chip 7...", 10)
            driver.get(self.url)
            
            # 1. Login
            self.progresso.emit("A abrir painel de login...", 15)
            try:
                btn_entrar_menu = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//*[contains(translate(text(), 'entrar', 'ENTRAR'), 'ENTRAR')]"))
                )
                btn_entrar_menu.click()
                time.sleep(2)
            except Exception:
                pass

            if self.email and self.senha:
                self.progresso.emit("A preencher dados de login...", 20)
                try:
                    email_input = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email'], input[name='email']"))
                    )
                    email_input.clear()
                    email_input.send_keys(self.email)
                    
                    senha_input = driver.find_element(By.CSS_SELECTOR, "input[type='password'], input[name='password']")
                    senha_input.clear()
                    senha_input.send_keys(self.senha)
                    time.sleep(1)
                    
                    btn_login = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                    btn_login.click()
                    
                    self.progresso.emit("Aguardando autenticação...", 30)
                    time.sleep(5)
                except Exception:
                    pass

            # 2. Carregar o curso
            self.progresso.emit("A carregar a página do curso...", 35)
            if driver.current_url != self.url:
                driver.get(self.url)
            time.sleep(5)

            self.progresso.emit("A identificar módulo e mapear aulas...", 40)
            mapper = Chip7Mapper(driver)
            if self.modo_avulso:
                nome_pedido = (self.opcoes.get("nome_aula") or "").strip()
                if not nome_pedido:
                    self.concluido.emit(
                        False,
                        "Digite o nome da aula. No Chip 7 o link do módulo é o mesmo para todas.",
                    )
                    return
                self.progresso.emit(f"A abrir no menu: {nome_pedido}", 42)
                titulo_avulso = self._abrir_aula_avulsa(driver, mapper, nome_pedido)
                if not titulo_avulso:
                    self.concluido.emit(
                        False,
                        f"Não encontrei '{nome_pedido}' na lista de aulas desse curso.",
                    )
                    return
                estrutura_curso = [{
                    "nome_curso": titulo_avulso,
                    "num_mod": 1,
                    "titulo_mod": "",
                    "aulas": [{
                        "num_aula": 1,
                        "titulo": titulo_avulso,
                        "url": "",
                        "texto_original": "",
                    }],
                }]
            else:
                estrutura_curso = mapper.mapear_curso()

            total_aulas = sum(len(m["aulas"]) for m in estrutura_curso)
            aulas_processadas = 0

            if total_aulas == 0:
                self.concluido.emit(False, "Nenhuma aula válida foi encontrada no menu. Verifique o link informado.")
                return

            # 3. Processamento e Downloads
            for modulo in estrutura_curso:
                if self._cancelado:
                    break
                self._checar_pausa()
                if self._cancelado:
                    break
                
                nome_curso_limpo = self._resolver_nome_curso(mapper, modulo)
                titulo_mod_limpo = mapper.limpar_nome(modulo['titulo_mod'])
                
                for aula in modulo["aulas"]:
                    if self._cancelado:
                        break
                    self._checar_pausa()
                    if self._cancelado:
                        break
                    aulas_processadas += 1
                    id_tabela = f"{aulas_processadas}"
                        
                    titulo_aula_limpo = mapper.limpar_nome(aula['titulo'], titulo_modulo=titulo_mod_limpo)
                    if self.modo_avulso:
                        pasta_aula = self.destino
                        nome_base_arquivo = titulo_aula_limpo or "Aula_Avulsa"
                    else:
                        pasta_aula, nome_base_arquivo = self._destino_da_aula(
                            nome_curso_limpo,
                            modulo["num_mod"],
                            titulo_mod_limpo,
                            aula["num_aula"],
                            titulo_aula_limpo,
                            aulas_processadas,
                        )
                    os.makedirs(pasta_aula, exist_ok=True)
                        
                    formato_download = self._formato_download()
                    caminho_template_ytdlp = os.path.join(pasta_aula, f"{nome_base_arquivo}.%(ext)s")
                    caminho_esperado_mp4 = os.path.join(
                        pasta_aula, f"{nome_base_arquivo}.{formato_download['ext']}"
                    )

                    self.item_concluido.emit({
                        "num": id_tabela,
                        "titulo": titulo_aula_limpo,
                        "caminho": caminho_esperado_mp4,
                        "status": "A localizar vídeo..."
                    })

                    # Navegação com fallback (Sidebar primeiro, depois página geral)
                    try:
                        if aula["url"] and aula["url"] != driver.current_url and not aula["url"].startswith("javascript:"):
                            driver.get(aula["url"])
                            time.sleep(3)
                        elif aula["texto_original"]:
                            texto_busca = re.sub(r'[\'"]', '', aula['texto_original']).strip()
                            if len(texto_busca) > 15:
                                texto_busca = texto_busca[:15]

                            alvo = None
                            try:
                                # Tenta encontrar no menu lateral
                                elementos_menu = driver.find_elements(
                                    By.XPATH, 
                                    f"//aside//*[contains(translate(text(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), '{texto_busca.upper()}')] | "
                                    f"//div[contains(@class, 'sidebar')]//*[contains(translate(text(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), '{texto_busca.upper()}')]"
                                )
                                for el in elementos_menu:
                                    if el.is_displayed():
                                        alvo = el
                                        break
                                
                                # Se não estiver no sidebar (ex: em visualização de grid), busca no corpo principal
                                if not alvo:
                                    elementos_gerais = driver.find_elements(
                                        By.XPATH, 
                                        f"//*[contains(translate(text(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), '{texto_busca.upper()}')]"
                                    )
                                    for el in elementos_gerais:
                                        if el.is_displayed() and not el.find_elements(By.XPATH, "./ancestor::header | ./ancestor::footer"):
                                            alvo = el
                                            break
                            except Exception:
                                pass

                            if alvo:
                                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", alvo)
                                time.sleep(0.5)
                                driver.execute_script("arguments[0].click();", alvo)
                                time.sleep(3)
                    except Exception:
                        pass

                    self._baixar_anexos_aula(driver, pasta_aula)
                    self._coletar_descricao_aula(
                        driver, 
                        modulo['num_mod'], 
                        titulo_mod_limpo, 
                        aula['num_aula'], 
                        titulo_aula_limpo
                    )

                    video_url = self.extrair_url_video(driver)

                    if not video_url:
                        self.item_progresso.emit(id_tabela, 100)
                        self.item_concluido.emit({
                            "num": id_tabela,
                            "titulo": titulo_aula_limpo,
                            "caminho": "-",
                            "status": "Ignorado (Sem vídeo)"
                        })
                        if self.modo_avulso:
                            self.concluido.emit(False, "Nenhum vídeo foi localizado na página.")
                            return
                        continue

                    ultima_atualizacao = [0]

                    def hook_download(d):
                        if self._cancelado:
                            raise DownloadCancelado()
                        if d['status'] == 'downloading':
                            percent_str = d.get('_percent_str', '0.0%')
                            percent_limpo = re.sub(r'\x1b\[[0-9;]*m', '', percent_str).strip()

                            speed_raw = d.get('_speed_str', '0 MiB/s')
                            eta_raw = d.get('_eta_str', '--:--')
                            speed_limpo = re.sub(r'\x1b\[[0-9;]*m', '', speed_raw).strip()
                            eta_limpo = re.sub(r'\x1b\[[0-9;]*m', '', eta_raw).strip()

                            texto_velocidade = f"{speed_limpo} | ETA: {eta_limpo}"

                            try:
                                pct_int = int(float(percent_limpo.replace('%', '').strip()))
                            except ValueError:
                                pct_int = 0

                            agora = time.time()
                            if agora - ultima_atualizacao[0] > 0.2:
                                ultima_atualizacao[0] = agora
                                self.item_progresso.emit(id_tabela, pct_int)
                                base_pct = int(((aulas_processadas - 1) / total_aulas) * 100)
                                atual_pct = int(base_pct + (pct_int / total_aulas))

                                self.progresso.emit(
                                    f"A descarregar ({aulas_processadas}/{total_aulas}): {titulo_aula_limpo[:25]} - {percent_limpo}",
                                    min(atual_pct, 99)
                                )

                                if hasattr(self, 'velocidade'):
                                    self.velocidade.emit(texto_velocidade)
                                    
                        self._checar_pausa()
                        if self._cancelado:
                            raise DownloadCancelado()

                    if self._cancelado:
                        break

                    if yt_dlp:
                        ydl_opts = {
                            'outtmpl': caminho_template_ytdlp,
                            'quiet': True,
                            'no_warnings': True,
                            'http_headers': {
                                'User-Agent': user_agent,
                                'Referer': driver.current_url
                            },
                            'progress_hooks': [hook_download],
                            **formato_download["ydl"],
                        }
                        
                        try:
                            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                                ydl.download([video_url])
                        except DownloadCancelado:
                            self._cancelado = True
                        except Exception as err:
                            causa = getattr(err, "__cause__", None)
                            if self._cancelado or isinstance(causa, DownloadCancelado):
                                self._cancelado = True
                            else:
                                print(f"Erro no download yt_dlp para aula '{titulo_aula_limpo}': {err}")

                    if self._cancelado:
                        break

                    self.item_progresso.emit(id_tabela, 100)
                    self.item_concluido.emit({
                        "num": id_tabela,
                        "titulo": titulo_aula_limpo,
                        "caminho": caminho_esperado_mp4,
                        "status": "Concluído"
                    })
                if self._cancelado:
                    break

            if self._cancelado:
                self.velocidade.emit("-- MiB/s | ETA: --:--")
                return

            if self.opcoes.get("gerar_txt", False) and self.relatorio_txt:
                caminho_txt = os.path.join(self.destino, "indice_e_descricao_curso.txt")
                try:
                    with open(caminho_txt, "w", encoding="utf-8") as f:
                        f.write("=== ÍNDICE E CONTEÚDO DO CURSO ===\n\n")
                        f.writelines(self.relatorio_txt)
                except Exception as err_txt:
                    print(f"Erro ao salvar arquivo .txt: {err_txt}")

            self.progresso.emit("Processo concluído!", 100)
            self.concluido.emit(True, "Processo concluído com sucesso!")

        except Exception as e:
            self.concluido.emit(False, f"Erro no motor do Chip 7: {str(e)}")
        finally:
            if driver:
                driver.quit()

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