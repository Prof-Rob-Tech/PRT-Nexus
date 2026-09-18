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


class Chip7Worker(QThread):
    progresso = Signal(str, int)
    velocidade = Signal(str)
    item_progresso = Signal(str, int)
    item_concluido = Signal(dict)
    concluido = Signal(bool, str)

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

    def extrair_url_video(self, driver):
        """Busca URLs de player em iframes, tags video ou scripts da página."""
        time.sleep(2)
        video_url = None

        # 1. Procura em iFrames
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        for iframe in iframes:
            try:
                src = iframe.get_attribute("src") or iframe.get_attribute("data-src") or ""
                if any(p in src.lower() for p in ["vimeo", "youtube", "panda", "wistia", "player", "embed", "converteai", "vturb", "bunny"]):
                    video_url = src
                    break
            except Exception:
                continue

        # 2. Procura em tags <video> ou <source>
        if not video_url:
            try:
                videos = driver.find_elements(By.TAG_NAME, "video")
                for v in videos:
                    src = v.get_attribute("src")
                    if src and not src.startswith("blob:"):
                        video_url = src
                        break
                    
                    # Procura tags <source> dentro do <video>
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

        return video_url

    def _baixar_anexos_aula(self, driver, pasta_destino):
        """Localiza e descarrega arquivos anexos (PDFs, ZIPs, Apostilas, etc.) da página da aula."""
        if not self.opcoes.get("baixar_anexos", False):
            return

        try:
            links = driver.find_elements(By.TAG_NAME, "a")
            extensoes_validas = ('.pdf', '.zip', '.rar', '.7z', '.epub', '.docx', '.xlsx', '.pptx', '.txt')
            
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
                            resp = requests.get(href, timeout=15)
                            if resp.status_code == 200:
                                with open(caminho_anexo, "wb") as f:
                                    f.write(resp.content)
                except Exception:
                    continue
        except Exception:
            pass

    def _coletar_descricao_aula(self, driver, num_mod, titulo_mod, num_aula, titulo_aula):
        """Coleta informações e descrições das aulas para compor o relatório .txt."""
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
            
            # 1. Painel de Login
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
            estrutura_curso = mapper.mapear_curso()

            total_aulas = sum(len(m["aulas"]) for m in estrutura_curso)
            aulas_processadas = 0

            if total_aulas == 0:
                self.concluido.emit(False, "Nenhuma aula válida foi encontrada no menu. Verifique o link informado.")
                return

            # 3. Processamento de Pastas e Downloads
            for modulo in estrutura_curso:
                self._checar_pausa()
                nome_curso_limpo = mapper.limpar_nome(modulo.get("nome_curso", "Chip 7 Conteudo"))
                
                # Se houver nome customizado vindo das opções, utiliza ele
                if self.opcoes.get("nome_conteudo"):
                    nome_curso_limpo = mapper.limpar_nome(self.opcoes.get("nome_conteudo"))

                titulo_mod_limpo = mapper.limpar_nome(modulo['titulo_mod'])

                pasta_curso = os.path.join(self.destino, f"01 - {nome_curso_limpo}")
                nome_pasta_modulo = f"{modulo['num_mod']:02d} - {titulo_mod_limpo}"
                caminho_pasta_modulo = os.path.join(pasta_curso, nome_pasta_modulo)
                
                os.makedirs(caminho_pasta_modulo, exist_ok=True)
                
                for aula in modulo["aulas"]:
                    self._checar_pausa()
                    aulas_processadas += 1
                    id_tabela = f"{aulas_processadas}"
                        
                    titulo_aula_limpo = mapper.limpar_nome(aula['titulo'])
                    nome_base_arquivo = f"{aula['num_aula']:02d} - {titulo_aula_limpo}"
                        
                    caminho_template_ytdlp = os.path.join(caminho_pasta_modulo, f"{nome_base_arquivo}.%(ext)s")
                    caminho_esperado_mp4 = os.path.join(caminho_pasta_modulo, f"{nome_base_arquivo}.mp4")

                    self.item_concluido.emit({
                        "num": id_tabela,
                        "titulo": titulo_aula_limpo,
                        "caminho": caminho_esperado_mp4,
                        "status": "A localizar vídeo..."
                    })

                    # Navegação até a aula
                    try:
                        if aula["url"] and aula["url"] != driver.current_url:
                            driver.get(aula["url"])
                            time.sleep(3)
                        elif aula["texto_original"]:
                            texto_busca = re.sub(r'[\'"]', '', aula['texto_original']).strip()
                            if len(texto_busca) > 15:
                                texto_busca = texto_busca[:15]

                            alvo = None
                            try:
                                elementos_pagina = driver.find_elements(
                                    By.XPATH, 
                                    f"//*[contains(translate(text(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), '{texto_busca.upper()}')]"
                                )
                                for el in elementos_pagina:
                                    if el.is_displayed():
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

                    # Processa anexos e texto para o arquivo .txt
                    self._baixar_anexos_aula(driver, caminho_pasta_modulo)
                    self._coletar_descricao_aula(
                        driver, 
                        modulo['num_mod'], 
                        titulo_mod_limpo, 
                        aula['num_aula'], 
                        titulo_aula_limpo
                    )

                    # Captura a URL do Vídeo
                    video_url = self.extrair_url_video(driver)

                    if not video_url:
                        self.item_progresso.emit(id_tabela, 100)
                        self.item_concluido.emit({
                            "num": id_tabela,
                            "titulo": titulo_aula_limpo,
                            "caminho": "-",
                            "status": "Ignorado (Sem vídeo)"
                        })
                        continue

                    # Download com yt_dlp
                    ultima_atualizacao = [0]

                    def hook_download(d):
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

                    if yt_dlp:
                        ydl_opts = {
                            'outtmpl': caminho_template_ytdlp,
                            'format': 'best[ext=mp4]/b/bestvideo+bestaudio/best',
                            'merge_output_format': 'mp4',
                            'quiet': True,
                            'no_warnings': True,
                            'http_headers': {
                                'User-Agent': user_agent,
                                'Referer': driver.current_url
                            },
                            'progress_hooks': [hook_download]
                        }
                        
                        try:
                            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                                ydl.download([video_url])
                        except Exception as err:
                            print(f"Erro no download yt_dlp para aula '{titulo_aula_limpo}': {err}")

                    self.item_progresso.emit(id_tabela, 100)
                    self.item_concluido.emit({
                        "num": id_tabela,
                        "titulo": titulo_aula_limpo,
                        "caminho": caminho_esperado_mp4,
                        "status": "Concluído"
                    })

            # Gera arquivo .txt no final, se a opção estiver marcada
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

    def resumir(self):
        self._mutex.lock()
        self._pausado = False
        self._condicao.wakeAll()
        self._mutex.unlock()

    def _checar_pausa(self):
        self._mutex.lock()
        while self._pausado:
            self.velocidade.emit("PAUSADO | ETA: --:--")
            self._condicao.wait(self._mutex)
        self._mutex.unlock()