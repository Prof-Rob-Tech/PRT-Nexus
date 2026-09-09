import os
import re
import time
from PySide6.QtCore import QThread, Signal
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

try:
    import yt_dlp
except ImportError:
    yt_dlp = None


class Chip7Mapper:
    # Marca do site e navegações globais para ignorar
    TERMOS_BLOQUEADOS = [
        "CHIP 7", "CHIP 7 CURSOS", "CHIP7", "CHIP7 CURSOS", "CHIP 7 - CURSOS",
        "BEM VINDO", "BEM-VINDO", "CURSOS EAD", "CURSOS PRESENCIAIS", 
        "CARRINHO", "CARRINHO DO ALUNO", "ENTRAR", "CRIAR CONTA", 
        "ÁREA DO ALUNO", "AREA DO ALUNO", "SAIR", "MINHA CONTA", 
        "MEUS CURSOS", "HOME", "INÍCIO", "INICIO", "CONTATO"
    ]

    # Títulos de cabeçalho das seções (não são links de vídeo)
    TITULOS_SECOES = [
        "MÉTODO CHIP", 
        "IPHONE X AO 13 PRO MAX", 
        "BÔNUS FACE ID"
    ]

    def __init__(self, driver=None):
        self.driver = driver

    def limpar_nome(self, texto):
        if not texto:
            return ""
        texto = re.sub(r'\.mp4$', '', texto, flags=re.IGNORECASE)
        texto = re.sub(r'[\\/*?:"<>|]', "", texto)
        return re.sub(r'\s+', ' ', texto).strip()

    def eh_termo_invalido(self, texto):
        if not texto:
            return True
        txt_upper = texto.upper().strip()
        
        # Ignora termos de sistema e a marca "CHIP 7"
        if any(termo == txt_upper or termo in txt_upper for termo in self.TERMOS_BLOQUEADOS):
            return True
            
        # Ignora se for título de seção sem aula
        if txt_upper in [s.upper() for s in self.TITULOS_SECOES]:
            return True
            
        return False

    def extrair_nome_modulo(self):
        """Captura o nome do módulo ('FACE ID 3.0')."""
        try:
            elementos = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Área do aluno') or contains(text(), 'Area do aluno')]")
            for el in elementos:
                texto = el.text.strip()
                if "/" in texto:
                    nome = texto.split("/")[-1].strip()
                    nome_limpo = self.limpar_nome(nome)
                    if nome_limpo and not self.eh_termo_invalido(nome_limpo):
                        return nome_limpo

            breadcrumbs = self.driver.find_elements(By.CSS_SELECTOR, ".breadcrumb, nav[aria-label='breadcrumb']")
            for bc in breadcrumbs:
                if "/" in bc.text:
                    nome = self.limpar_nome(bc.text.split("/")[-1])
                    if nome and not self.eh_termo_invalido(nome):
                        return nome
        except Exception:
            pass
        return "FACE ID 3.0"

    def mapear_curso(self, driver=None):
        if driver:
            self.driver = driver

        nome_modulo = self.extrair_nome_modulo()
        aulas = []
        vistos = set()

        # Busca links preferencialmente do menu lateral ou da página
        elementos_a = self.driver.find_elements(By.XPATH, "//aside//a | //div[contains(@class, 'sidebar')]//a | //div[contains(@class, 'menu')]//a | //ul//li//a | //a")

        for elem in elementos_a:
            try:
                txt_bruto = elem.text.strip().split('\n')[0]
                txt = self.limpar_nome(txt_bruto)
                href = elem.get_attribute("href") or ""

                # Descarta se o texto for muito curto ou for termo bloqueado
                if not txt or len(txt) < 3 or self.eh_termo_invalido(txt):
                    continue

                # Descarta links de sistema ou topo/carrinho
                if any(ign in href for ign in ["/carrinho", "/login", "/presencial", "cart", "/sair", "/conta", "whatsapp"]):
                    continue

                # Evita capturar o nome do módulo principal como aula
                if txt.upper() == nome_modulo.upper():
                    continue

                if txt not in vistos:
                    vistos.add(txt)
                    aulas.append({
                        "num_aula": len(aulas) + 1,
                        "titulo": txt,
                        "url": href,
                        "texto_original": txt_bruto
                    })

            except Exception:
                continue

        return [{
            "num_mod": 1,
            "titulo_mod": nome_modulo,
            "aulas": aulas
        }]


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
                time.sleep(6)
            except Exception:
                pass

            self.progresso.emit("A carregar a página do curso...", 35)
            driver.get(self.url)
            time.sleep(6)

            self.progresso.emit("A identificar módulo e mapear aulas...", 40)
            
            mapper = Chip7Mapper(driver)
            estrutura_curso = mapper.mapear_curso()

            total_aulas = sum(len(m["aulas"]) for m in estrutura_curso)
            aulas_processadas = 0

            if total_aulas == 0:
                self.concluido.emit(False, "Nenhuma aula foi encontrada na página. Verifique o link informado.")
                return

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
                        "status": "A localizar vídeo..."
                    })

                    try:
                        if aula["url"] and aula["url"] != driver.current_url:
                            driver.get(aula["url"])
                            time.sleep(5)
                        elif aula["texto_original"]:
                            alvo = driver.find_element(By.XPATH, f"//*[contains(text(), '{aula['texto_original'][:15]}')]")
                            driver.execute_script("arguments[0].click();", alvo)
                            time.sleep(5)
                    except Exception:
                        pass

                    video_url = None
                    time.sleep(3)
                    
                    iframes = driver.find_elements(By.TAG_NAME, "iframe")
                    for iframe in iframes:
                        src = iframe.get_attribute("src") or iframe.get_attribute("data-src") or ""
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
                        
                        try:
                            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                                ydl.download([video_url])
                        except Exception as err:
                            print(f"Erro no download yt_dlp: {err}")

                    self.item_progresso.emit(id_tabela, 100)
                    self.item_concluido.emit({
                        "num": id_tabela,
                        "titulo": aula['titulo'],
                        "caminho": caminho_arquivo,
                        "status": "Concluído"
                    })

            self.progresso.emit("Processo concluído!", 100)
            self.concluido.emit(True, "Processo concluído com sucesso!")

        except Exception as e:
            self.concluido.emit(False, f"Erro no motor do Chip 7: {str(e)}")
        finally:
            if driver:
                driver.quit()