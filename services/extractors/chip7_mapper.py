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
    # Subcategorias conhecidas (Verde) que viram subpastas
    SUBCATEGORIAS_CONHECIDAS = [
        "MÉTODO CHIP", "METODO CHIP",
        "IPHONE X AO 13 PRO MAX", "IPHONE X A 13 PRO MAX",
        "BÔNUS FACE ID", "BONUS FACE ID"
    ]

    # Termos e URLs globais a serem ignorados
    TRECHOS_BLOQUEADOS = [
        "SE ESPECIALIZE", "TREINAMENTOS", "WHATSAPP", "INSTAGRAM", "YOUTUBE",
        "FACEBOOK", "TELEGRAM", "TIKTOK", "CARRINHO", "MINHA CONTA",
        "MEUS CURSOS", "ÁREA DO ALUNO", "AREA DO ALUNO", "FALE CONOSCO",
        "ATENDIMENTO", "POLÍTICA DE PRIVACIDADE", "TERMOS DE USO",
        "TODOS OS DIREITOS", "DIREITOS RESERVADOS", "LOGOUT", "SAIR",
        "BEM VINDO", "BEM-VINDO", "CURSOS EAD", "CURSOS PRESENCIAIS",
        "MEUS CERTIFICADOS", "DÚVIDAS", "DUVIDAS", "MEU PERFIL"
    ]

    DOMINIOS_BLOQUEADOS = [
        "instagram.com", "youtube.com", "youtu.be", "facebook.com", 
        "whatsapp.com", "api.whatsapp.com", "wa.me", "t.me", "telegram.org", 
        "tiktok.com", "twitter.com"
    ]

    URL_PALAVRAS_BLOQUEADAS = [
        "/carrinho", "/login", "/presencial", "/sair", "/conta", "whatsapp", 
        "/logout", "/perfil", "/certificados", "tel:", "mailto:"
    ]

    def __init__(self, driver=None):
        self.driver = driver

    def limpar_nome(self, texto):
        if not texto:
            return ""
        texto = re.sub(r'\.mp4$', '', texto, flags=re.IGNORECASE)
        texto = re.sub(r'[\\/*?:"<>|]', "", texto)
        return re.sub(r'\s+', ' ', texto).strip()

    def eh_termo_invalido(self, texto, href=""):
        if not texto:
            return True
        txt_upper = texto.upper().strip()
        href_lower = href.lower() if href else ""

        if re.search(r'\(?\d{2}\)?\s*9?\s*\d{4,5}[-\s\.]?\d{4}', texto):
            return True

        if any(dom in href_lower for dom in self.DOMINIOS_BLOQUEADOS):
            return True
        if any(ign in href_lower for ign in self.URL_PALAVRAS_BLOQUEADAS):
            return True

        if any(trecho in txt_upper for trecho in self.TRECHOS_BLOQUEADOS):
            return True

        return False

    def expandir_modulos(self):
        """Abre sanfonas/módulos para revelar as aulas antes de mapear."""
        try:
            botoes = self.driver.find_elements(
                By.XPATH, 
                "//*[contains(@class, 'accordion') or contains(@class, 'collapse') or contains(@class, 'modulo') or contains(@class, 'folder') or contains(@class, 'card-header')]"
            )
            for btn in botoes:
                try:
                    if btn.is_displayed():
                        self.driver.execute_script("arguments[0].click();", btn)
                        time.sleep(0.3)
                except Exception:
                    continue
        except Exception:
            pass

    def extrair_nome_modulo(self):
        try:
            elementos = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Área do aluno') or contains(text(), 'Area do aluno')]")
            for el in elementos:
                texto = el.text.strip()
                if "/" in texto:
                    nome = texto.split("/")[-1].strip()
                    nome_limpo = self.limpar_nome(nome)
                    if nome_limpo and not self.eh_termo_invalido(nome_limpo):
                        return nome_limpo
        except Exception:
            pass
        return "FACE ID 3.0"

    def mapear_curso(self, driver=None):
        if driver:
            self.driver = driver

        self.expandir_modulos()
        time.sleep(2)

        nome_modulo = self.extrair_nome_modulo()

        # Script JS ordenado verticalmente para varrer o menu lateral
        js_script = """
        return (function() {
            let items = [];
            let rawElements = document.querySelectorAll('aside *, .sidebar *, [class*="sidebar"] *, [class*="menu"] *, [class*="playlist"] *, [class*="aula"] *, [class*="lesson"] *, a, li, p, span, div, h1, h2, h3, h4, h5, h6');
            let widthThreshold = window.innerWidth * 0.40;

            rawElements.forEach(el => {
                let rect = el.getBoundingClientRect();
                
                if (rect.width === 0 || rect.height === 0 || rect.top < 120 || rect.left > widthThreshold) {
                    return;
                }

                let children = Array.from(el.children);
                let temFilhoComTexto = children.some(c => {
                    let r = c.getBoundingClientRect();
                    let t = c.innerText ? c.innerText.trim() : '';
                    return r.width > 0 && r.height > 0 && t.length > 0 && 
                           ['DIV', 'A', 'LI', 'UL', 'P', 'H1', 'H2', 'H3', 'H4', 'H5', 'SECTION', 'NAV', 'SPAN'].includes(c.tagName);
                });

                if (temFilhoComTexto) return;

                let txt = el.innerText ? el.innerText.trim() : '';
                if (!txt) return;

                txt = txt.replace(/\\s+/g, ' ');

                if (txt.length >= 2 && txt.length <= 150) {
                    let href = el.getAttribute('href') || (el.tagName === 'A' ? el.href : '');
                    let cls = (el.className || '') + ' ' + (el.parentElement ? el.parentElement.className || '' : '');
                    items.push({
                        text: txt,
                        href: href || '',
                        tag: el.tagName,
                        className: cls,
                        top: rect.top
                    });
                }
            });

            // Ordena os elementos do topo para o fundo
            items.sort((a, b) => a.top - b.top);
            return items;
        })();
        """

        candidatos_js = self.driver.execute_script(js_script) or []

        subcategorias = []
        subcat_atual = {
            "num_sub": 1,
            "titulo_sub": "Geral",
            "aulas": []
        }
        vistos_aulas = set()
        vistos_subcats = set()

        for cand in candidatos_js:
            txt = self.limpar_nome(cand["text"])
            href = cand["href"]

            if len(txt) < 2 or len(txt) > 150:
                continue

            if self.eh_termo_invalido(txt, href):
                continue

            txt_upper = txt.upper()
            if txt_upper == nome_modulo.upper() or txt_upper in ["ÁREA DO ALUNO", "AREA DO ALUNO", "FACE ID 3.0"]:
                continue

            # Verifica se o elemento é um cabeçalho de categoria (Verde)
            e_subcat = False
            if txt_upper in self.SUBCATEGORIAS_CONHECIDAS:
                e_subcat = True
            elif cand["tag"] in ['H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'HEADER', 'STRONG'] or any(k in cand["className"].lower() for k in ['header', 'title', 'categoria', 'cat-title', 'section-title']):
                if not any(k in txt_upper for k in ["AULA", "TRANSPLANTE", "REPARO", "PROGRAMAÇÃO", "REPROGRAMAÇÃO", "FLEX"]):
                    e_subcat = True

            if e_subcat:
                if txt not in vistos_subcats:
                    vistos_subcats.add(txt)
                    # Salva a subcategoria anterior se ela tiver aulas
                    if subcat_atual["aulas"]:
                        subcategorias.append(subcat_atual)

                    subcat_atual = {
                        "num_sub": len(subcategorias) + 1,
                        "titulo_sub": txt,
                        "aulas": []
                    }
                continue

            # Se for uma aula real (Azul)
            if txt not in vistos_aulas:
                vistos_aulas.add(txt)
                subcat_atual["aulas"].append({
                    "num_aula": len(subcat_atual["aulas"]) + 1,
                    "titulo": txt,
                    "url": href if href and not href.endswith("#") and "javascript:" not in href else "",
                    "texto_original": cand["text"]
                })

        # Adiciona a última subcategoria
        if subcat_atual["aulas"]:
            subcategorias.append(subcat_atual)

        return [{
            "num_mod": 1,
            "titulo_mod": nome_modulo,
            "subcategorias": subcategorias
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
                time.sleep(8)
            except Exception:
                pass

            self.progresso.emit("A carregar a página do curso...", 35)
            driver.get(self.url)
            time.sleep(8)

            self.progresso.emit("A identificar módulo e mapear aulas...", 40)
            
            mapper = Chip7Mapper(driver)
            estrutura_curso = mapper.mapear_curso()

            total_aulas = 0
            for m in estrutura_curso:
                for sub in m["subcategorias"]:
                    total_aulas += len(sub["aulas"])

            aulas_processadas = 0

            if total_aulas == 0:
                self.concluido.emit(False, "Nenhuma aula válida foi encontrada no menu. Verifique o link informado.")
                return

            for modulo in estrutura_curso:
                nome_pasta_modulo = f"{modulo['num_mod']:02d} - {modulo['titulo_mod']}"
                caminho_pasta_modulo = os.path.join(self.destino, nome_pasta_modulo)
                os.makedirs(caminho_pasta_modulo, exist_ok=True)

                for sub in modulo["subcategorias"]:
                    nome_pasta_sub = f"{sub['num_sub']:02d} - {sub['titulo_sub']}"
                    caminho_pasta_sub = os.path.join(caminho_pasta_modulo, nome_pasta_sub)
                    os.makedirs(caminho_pasta_sub, exist_ok=True)

                    for aula in sub["aulas"]:
                        aulas_processadas += 1
                        id_tabela = f"{aulas_processadas}"
                        
                        nome_arquivo_video = f"{aula['num_aula']:02d} - {aula['titulo']}.mp4"
                        caminho_arquivo = os.path.join(caminho_pasta_sub, nome_arquivo_video)

                        self.item_concluido.emit({
                            "num": id_tabela,
                            "titulo": f"[{sub['titulo_sub']}] {aula['titulo']}",
                            "caminho": caminho_arquivo,
                            "status": "A localizar vídeo..."
                        })

                        try:
                            if aula["url"] and aula["url"] != driver.current_url:
                                driver.get(aula["url"])
                                time.sleep(4)
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
                                        if el.is_displayed() and el.location['x'] < 400 and el.location['y'] > 120:
                                            alvo = el
                                            break
                                except Exception:
                                    pass

                                if alvo:
                                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", alvo)
                                    time.sleep(0.5)
                                    driver.execute_script("arguments[0].click();", alvo)
                                    time.sleep(4)
                        except Exception:
                            pass

                        video_url = None
                        time.sleep(2)
                        
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
                                "titulo": f"[{sub['titulo_sub']}] {aula['titulo']}",
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
                            "titulo": f"[{sub['titulo_sub']}] {aula['titulo']}",
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