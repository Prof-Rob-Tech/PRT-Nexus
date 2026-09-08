import os
import time
import re
from PySide6.QtCore import QThread, Signal
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

try:
    import yt_dlp
except ImportError:
    yt_dlp = None


class Chip7Worker(QThread):
    progresso = Signal(str, int)
    item_progresso = Signal(str, int)
    item_concluido = Signal(dict)
    concluido = Signal(bool, str)

    def __init__(self, url, email, senha, destino, modo_avulso=False, parent=None):
        super().__init__(parent)
        self.url = url
        self.email = email
        self.senha = senha
        self.destino = destino
        self.modo_avulso = modo_avulso

    def limpar_nome(self, texto):
        if not texto:
            return ""
        texto = re.sub(r'\.mp4$', '', texto, flags=re.IGNORECASE)
        texto = re.sub(r'[\\/*?:"<>|]', "", texto)
        return re.sub(r'\s+', ' ', texto).strip()

    def run(self):
        driver = None
        try:
            os.makedirs(self.destino, exist_ok=True)

            self.progresso.emit("A iniciar o Google Chrome...", 5)
            
            options = webdriver.ChromeOptions()
            options.add_argument("--start-maximized")
            driver = webdriver.Chrome(options=options)
            
            self.progresso.emit("A aceder ao Chip 7...", 10)
            driver.get(self.url)
            
            self.progresso.emit("A abrir painel de login...", 15)
            try:
                btn_entrar_menu = WebDriverWait(driver, 8).until(
                    EC.element_to_be_clickable((By.XPATH, "//*[contains(translate(text(), 'entrar', 'ENTRAR'), 'ENTRAR')]"))
                )
                btn_entrar_menu.click()
                time.sleep(2)
            except Exception:
                pass

            self.progresso.emit("A preencher dados de login...", 20)
            try:
                email_input = WebDriverWait(driver, 8).until(
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

            self.progresso.emit("A aceder ao conteúdo do curso...", 35)
            driver.get(self.url)
            time.sleep(5)

            self.progresso.emit("A mapear aulas da barra lateral...", 40)
            time.sleep(3)
            
            # Busca especificamente os elementos da lista lateral do curso
            elementos_menu = driver.find_elements(By.CSS_SELECTOR, "aside a, aside button, .sidebar a, .sidebar button, div[class*='lesson'] a, div[class*='aula'] a, a[href*='/aluno/']")
            
            aulas = []
            termos_bloqueados = ["BEM VINDO", "CURSOS EAD", "CURSOS PRESENCIAIS", "CARRINHO", "ENTRAR", "CRIAR CONTA", "ÁREA DO ALUNO", "SAIR"]
            
            for elem in elementos_menu:
                try:
                    txt = self.limpar_nome(elem.text.split('\n')[0])
                    href = elem.get_attribute("href") or ""
                    
                    # Ignora links do topo e páginas externas/da loja
                    if any(termo in txt.upper() for termo in termos_bloqueados):
                        continue
                    if any(ignorar in href for ignorar in ["/presencial", "/carrinho", "/login"]):
                        continue

                    if txt and len(txt) > 2:
                        aulas.append({
                            "num_aula": len(aulas) + 1,
                            "titulo": txt,
                            "url": href if href != driver.current_url else None,
                            "texto_original": elem.text.strip().split('\n')[0]
                        })
                except Exception:
                    continue

            if aulas:
                estrutura_curso = [{
                    "num_mod": 1,
                    "titulo_mod": "Curso Completo",
                    "aulas": aulas
                }]
            else:
                titulo_pag = self.limpar_nome(driver.title or "Aula_Chip7")
                estrutura_curso = [{
                    "num_mod": 1,
                    "titulo_mod": "Módulo Único",
                    "aulas": [{
                        "num_aula": 1,
                        "titulo": titulo_pag,
                        "url": driver.current_url,
                        "texto_original": None
                    }]
                }]

            total_aulas = sum(len(m["aulas"]) for m in estrutura_curso)
            aulas_processadas = 0

            for modulo in estrutura_curso:
                nome_pasta_modulo = f"{modulo['num_mod']:02d} - {modulo['titulo_mod']}"
                caminho_pasta_modulo = os.path.join(self.destino, nome_pasta_modulo)
                os.makedirs(caminho_pasta_modulo, exist_ok=True)

                for aula in modulo["aulas"]:
                    aulas_processadas += 1
                    id_tabela = f"{aulas_processadas}"
                    
                    nome_arquivo_video = f"{aula['num_aula']:02d} - {aula['titulo']}.mp4"
                    caminho_arquivo = os.path.join(caminho_pasta_modulo, nome_arquivo_video)

                    self.item_concluido.emit({
                        "num": id_tabela,
                        "titulo": aula['titulo'],
                        "caminho": caminho_arquivo,
                        "status": "A carregar..."
                    })

                    try:
                        if aula["url"]:
                            driver.get(aula["url"])
                            time.sleep(4)
                        elif aula["texto_original"]:
                            alvo = driver.find_element(By.XPATH, f"//*[contains(text(), '{aula['texto_original'][:15]}')]")
                            driver.execute_script("arguments[0].click();", alvo)
                            time.sleep(4)
                    except Exception:
                        pass

                    video_url = None
                    iframes = driver.find_elements(By.TAG_NAME, "iframe")
                    for iframe in iframes:
                        src = iframe.get_attribute("src") or ""
                        if any(p in src for p in ["vimeo", "youtube", "panda", "wistia", "player", "embed", "converteai"]):
                            video_url = src
                            break

                    if not video_url:
                        videos = driver.find_elements(By.TAG_NAME, "video")
                        for v in videos:
                            src = v.get_attribute("src")
                            if src:
                                video_url = src
                                break

                    if not video_url:
                        self.item_progresso.emit(id_tabela, 100)
                        self.item_concluido.emit({
                            "num": id_tabela,
                            "titulo": aula['titulo'],
                            "caminho": "-",
                            "status": "Ignorado (Sem vídeo)"
                        })
                        continue

                    ultima_atualizacao = [0]

                    def hook_download(d):
                        if d['status'] == 'downloading':
                            percent_str = d.get('_percent_str', '0.0%')
                            percent_limpo = re.sub(r'\x1b\[[0-9;]*m', '', percent_str).strip()
                            
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
                                    f"A descarregar ({aulas_processadas}/{total_aulas}): {aula['titulo']} - {percent_limpo}", 
                                    min(atual_pct, 99)
                                )

                        elif d['status'] == 'finished':
                            self.item_progresso.emit(id_tabela, 100)

                    if yt_dlp:
                        ydl_opts = {
                            'outtmpl': caminho_arquivo,
                            'format': 'best[ext=mp4]/b/bestvideo+bestaudio/best',
                            'merge_output_format': 'mp4',
                            'quiet': True,
                            'no_warnings': True,
                            'http_headers': {
                                'Referer': driver.current_url
                            },
                            'progress_hooks': [hook_download]
                        }
                        
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            ydl.download([video_url])

                    self.item_progresso.emit(id_tabela, 100)
                    self.item_concluido.emit({
                        "num": id_tabela,
                        "titulo": aula['titulo'],
                        "caminho": caminho_arquivo,
                        "status": "Concluído"
                    })

            self.progresso.emit("Aulas descarregadas com sucesso!", 100)
            self.concluido.emit(True, "Processo concluído com sucesso!")

        except Exception as e:
            self.concluido.emit(False, f"Erro no motor do Chip 7: {str(e)}")
        finally:
            if driver:
                driver.quit()