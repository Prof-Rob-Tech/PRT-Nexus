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

    def run(self):
        driver = None
        try:
            os.makedirs(self.destino, exist_ok=True)

            self.progresso.emit("A iniciar o Google Chrome...", 10)
            
            options = webdriver.ChromeOptions()
            driver = webdriver.Chrome(options=options)
            
            self.progresso.emit("A aceder ao Chip 7...", 20)
            driver.get(self.url)
            
            # 1. Clicar no botão "ENTRAR"
            self.progresso.emit("A abrir painel de login...", 30)
            btn_entrar_menu = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//*[contains(translate(text(), 'entrar', 'ENTRAR'), 'ENTRAR')]"))
            )
            btn_entrar_menu.click()
            time.sleep(2) 
            
            # 2. Preencher os dados de login
            self.progresso.emit("A preencher dados de login...", 40)
            email_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email'], input[name='email']"))
            )
            email_input.send_keys(self.email)
            
            senha_input = driver.find_element(By.CSS_SELECTOR, "input[type='password'], input[name='password']")
            senha_input.send_keys(self.senha)
            time.sleep(1)
            
            btn_login = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            btn_login.click()
            
            self.progresso.emit("Aguardando autenticação...", 50)
            time.sleep(5) 

            # 3. Navegar diretamente para o curso/aula
            self.progresso.emit("A aceder à página do curso...", 60)
            driver.get(self.url)
            time.sleep(5)

            # 4. CAPTURA E EXTRAÇÃO DO VÍDEO
            self.progresso.emit("A localizar o player de vídeo...", 70)

            try:
                titulo_pagina = driver.title or "Aula_Chip7"
                titulo_limpo = re.sub(r'[\\/*?:"<>|]', "", titulo_pagina).strip()
            except Exception:
                titulo_limpo = "Aula_Chip7"

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
                video_url = driver.current_url

            self.progresso.emit(f"A descarregar vídeo: {titulo_limpo}...", 80)
            caminho_arquivo = os.path.join(self.destino, f"{titulo_limpo}.mp4")

            # Cria a linha na tabela UMA ÚNICA VEZ antes do download
            self.item_concluido.emit({
                "num": "1",
                "titulo": titulo_limpo,
                "caminho": caminho_arquivo,
                "status": "A iniciar..."
            })

            # Controle de atualização para evitar travamento
            ultima_atualizacao = [0]

            def hook_download(d):
                if d['status'] == 'downloading':
                    percent_str = d.get('_percent_str', '0.0%')
                    # Limpa caracteres invisíveis que o terminal gera
                    percent_limpo = re.sub(r'\x1b\[[0-9;]*m', '', percent_str).strip()
                    
                    try:
                        # Extrai apenas o número inteiro (ex: 51.9 -> 51)
                        pct_int = int(float(percent_limpo.replace('%', '').strip()))
                    except ValueError:
                        pct_int = 0

                    agora = time.time()
                    if agora - ultima_atualizacao[0] > 0.2:
                        ultima_atualizacao[0] = agora
                        
                        # Envia o inteiro limpo para animar a célula de Status
                        # Enviamos pelos dois IDs prováveis para garantir que a interface apanha
                        self.item_progresso.emit("1", pct_int)
                        self.item_progresso.emit(titulo_limpo, pct_int)
                        
                        # Atualiza a barra geral principal
                        progresso_geral = int(80 + (pct_int * 0.15))
                        self.progresso.emit(f"A descarregar: {titulo_limpo} - {percent_limpo}", progresso_geral)

                elif d['status'] == 'finished':
                    self.item_progresso.emit("1", 100)
                    self.item_progresso.emit(titulo_limpo, 100)
                    self.progresso.emit("A finalizar arquivo de vídeo...", 95)

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
            else:
                raise Exception("A biblioteca 'yt-dlp' não está instalada.")

            # Finaliza o processo, atualiza barra para 100% e célula para "Concluído"
            self.item_progresso.emit("1", 100)
            self.item_progresso.emit(titulo_limpo, 100)
            
            self.item_concluido.emit({
                "num": "1",
                "titulo": titulo_limpo,
                "caminho": caminho_arquivo,
                "status": "Concluído"
            })

            self.progresso.emit("Processo Finalizado!", 100)
            self.concluido.emit(True, "Vídeo do Chip 7 descarregado com sucesso!")

        except Exception as e:
            self.concluido.emit(False, f"Erro no motor do Chip 7: {str(e)}")
        finally:
            if driver:
                driver.quit()