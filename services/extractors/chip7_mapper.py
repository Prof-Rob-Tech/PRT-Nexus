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

            self.progresso.emit("A mapear módulos e aulas do menu lateral...", 40)
            time.sleep(3) # Dá tempo para a barra lateral carregar completamente
            
            seletor_modulos = "[class*='module'], [class*='modulo'], [class*='accordion'], [class*='section'], .sidebar div[class*='group']"
            modulos_elems = driver.find_elements(By.CSS_SELECTOR, seletor_modulos)
            
            estrutura_curso = []

            if modulos_elems:
                for idx_m, mod_elem in enumerate(modulos_elems, 1):
                    try:
                        try:
                            mod_elem.click()
                            time.sleep(0.5)
                        except Exception:
                            pass

                        texto_bruto = mod_elem.text.split('\n')[0].strip() if mod_elem.text else f"Modulo_{idx_m}"
                        mod_titulo = self.limpar_nome(texto_bruto) or f"Modulo_{idx_m}"

                        aulas_elems = mod_elem.find_elements(By.CSS_SELECTOR, "a, button, li, [class*='lesson'], [class*='aula']")
                        aulas = []

                        for idx_a, aula_elem in enumerate(aulas_elems, 1):
                            href = aula_elem.get_attribute("href")
                            texto_aula = aula_elem.text.strip().split('\n')[0] if aula_elem.text else ""
                            
                            if not texto_aula:
                                continue
                                
                            nome_aula_limpo = self.limpar_nome(texto_aula)
                            if not nome_aula_limpo or nome_aula_limpo == mod_titulo:
                                continue

                            aulas.append({
                                "num_aula": len(aulas) + 1,
                                "titulo": nome_aula_limpo,
                                "url": href,
                                "xpath": f"(//*[contains(text(), '{texto_aula[:15]}')])[1]"
                            })

                        if aulas:
                            estrutura_curso.append({
                                "num_mod": idx_m,
                                "titulo_mod": mod_titulo,
                                "aulas": aulas
                            })
                    except Exception:
                        continue

            if not estrutura_curso:
                links_aulas = driver.find_elements(By.CSS_SELECTOR, "aside a, nav a, .sidebar a")
                aulas_fallback = []
                for idx_a, link in enumerate(links_aulas, 1):
                    txt = self.limpar_nome(link.text.split('\n')[0])
                    href = link.get_attribute("href")
                    if txt and href:
                        aulas_fallback.append({
                            "num_aula": idx_a,
                            "titulo": txt,
                            "url": href,
                            "xpath": None
                        })
                if aulas_fallback:
                    estrutura_curso = [{
                        "num_mod": 1,
                        "titulo_mod": "Modulo_Geral",
                        "aulas": aulas_fallback
                    }]

            if not estrutura_curso:
                titulo_pag = self.limpar_nome(driver.title or "Aula_Chip7")
                estrutura_curso = [{
                    "num_mod": 1,
                    "titulo_mod": "Módulo Único",
                    "aulas": [{
                        "num_aula": 1,
                        "titulo": titulo_pag,
                        "url": driver.current_url,
                        "xpath": None
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
                        "titulo": f"[{modulo['titulo_mod']}] {aula['titulo']}",
                        "caminho": caminho_arquivo,
                        "status": "A carregar..."
                    })

                    try:
                        if aula["url"] and aula["url"] != driver.current_url:
                            driver.get(aula["url"])
                            time.sleep(5) # Espera a página e o iframe carregarem
                        elif aula["xpath"]:
                            elem_clique = driver.find_element(By.XPATH, aula["xpath"])
                            elem_clique.click()
                            time.sleep(5)
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

                    # SE NÃO ENCONTRAR VÍDEO, PULA A AULA EM VEZ DE DAR ERRO
                    if not video_url:
                        self.item_progresso.emit(id_tabela, 100)
                        self.item_concluido.emit({
                            "num": id_tabela,
                            "titulo": f"[{modulo['titulo_mod']}] {aula['titulo']}",
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
                        "titulo": f"[{modulo['titulo_mod']}] {aula['titulo']}",
                        "caminho": caminho_arquivo,
                        "status": "Concluído"
                    })

            self.progresso.emit("Todos os módulos e aulas foram descarregados!", 100)
            self.concluido.emit(True, "Processo concluído com sucesso!")

        except Exception as e:
            self.concluido.emit(False, f"Erro no motor do Chip 7: {str(e)}")
        finally:
            if driver:
                driver.quit()