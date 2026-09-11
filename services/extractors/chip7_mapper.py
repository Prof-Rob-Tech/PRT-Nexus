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
    TERMOS_EXACT_BLOQUEADOS = {
        "SE ESPECIALIZE", "TREINAMENTOS", "WHATSAPP", "INSTAGRAM", "YOUTUBE",
        "FACEBOOK", "TELEGRAM", "TIKTOK", "CARRINHO", "MINHA CONTA",
        "MEUS CURSOS", "ÁREA DO ALUNO", "AREA DO ALUNO", "FALE CONOSCO",
        "ATENDIMENTO", "POLÍTICA DE PRIVACIDADE", "TERMOS DE USO",
        "TODOS OS DIREITOS", "DIREITOS RESERVADOS", "LOGOUT", "SAIR",
        "BEM VINDO", "BEM-VINDO", "CURSOS PRESENCIAIS", "CURSOS EAD", "CURSO EAD",
        "MEUS CERTIFICADOS", "DÚVIDAS", "DUVIDAS", "MEU PERFIL", "CONECTOR CHIP 7",
        "INÍCIO", "INICIO", "HOME", "MÓDULOS", "MODULOS", "VER CURSO", "CONTINUAR", "ENTRAR",
        "SUPORTE", "CONTATO"
    }

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

        apenas_digitos = re.sub(r'\D', '', texto)
        if len(apenas_digitos) in [10, 11] and re.search(r'^\(?\d{2}\)?', texto.strip()):
            return True
        if re.search(r'\(?\d{2}\)?[\s\.\-]*9?[\s\.\-]*\d{1,5}[\s\.\-]*\d{3,4}', texto):
            return True

        if any(dom in href_lower for dom in self.DOMINIOS_BLOQUEADOS):
            return True
        if any(ign in href_lower for ign in self.URL_PALAVRAS_BLOQUEADAS):
            return True

        if txt_upper in self.TERMOS_EXACT_BLOQUEADOS:
            return True

        return False

    def expandir_modulos(self):
        try:
            botoes = self.driver.find_elements(
                By.XPATH, 
                "//*[contains(@class, 'accordion') or contains(@class, 'collapse') or contains(@class, 'modulo') or contains(@class, 'folder') or contains(@class, 'card-header') or contains(@class, 'toggle') or @data-toggle='collapse' or @data-bs-toggle='collapse']"
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
            h_tags = self.driver.find_elements(By.XPATH, "//h1 | //h2 | //h3")
            for h in h_tags:
                if h.is_displayed():
                    txt = self.limpar_nome(h.text)
                    if txt and len(txt) > 3 and not self.eh_termo_invalido(txt):
                        return txt
        except Exception:
            pass

        try:
            page_title = self.driver.title
            if page_title:
                nome = page_title.split("-")[0].split("|")[0].strip()
                nome_limpo = self.limpar_nome(nome)
                if nome_limpo and len(nome_limpo) > 3 and not self.eh_termo_invalido(nome_limpo):
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

        js_script = """
        return (function() {
            let items = [];
            let elements = Array.from(document.querySelectorAll('a, button, li, h1, h2, h3, h4, h5, div.card-header, div.accordion-header, [class*="modulo"], [class*="aula"], [class*="lesson"]'));

            elements.forEach(el => {
                let rect = el.getBoundingClientRect();
                if (rect.width === 0 && rect.height === 0) return;

                let txt = el.innerText ? el.innerText.trim() : '';
                if (!txt) return;

                let lines = txt.split('\\n').map(l => l.trim()).filter(l => l.length > 0);
                if (lines.length === 0) return;

                let firstLine = lines[0];
                if (firstLine.length < 2 || firstLine.length > 120) return;

                let href = el.getAttribute('href') || (el.tagName === 'A' ? el.href : '') || '';
                let tag = el.tagName.toUpperCase();
                let cls = (el.className && typeof el.className === 'string') ? el.className.toLowerCase() : '';

                let isHeaderTag = ['H1', 'H2', 'H3', 'H4', 'H5'].includes(tag);
                let isHeaderClass = cls.includes('card-header') || cls.includes('accordion') || cls.includes('modulo-header') || cls.includes('folder') || cls.includes('section');
                let hasToggle = el.hasAttribute('data-toggle') || el.hasAttribute('data-bs-toggle') || el.hasAttribute('aria-expanded');

                items.push({
                    text: firstLine,
                    href: href,
                    isSubHeader: isHeaderTag || isHeaderClass || hasToggle,
                    top: rect.top + window.scrollY
                });
            });

            items.sort((a, b) => a.top - b.top);
            return items;
        })();
        """

        candidatos_js = self.driver.execute_script(js_script) or []

        subcategorias = []
        subcat_atual = None
        vistos_na_sub = set()
        nomes_sub_criadas = set()

        for cand in candidatos_js:
            txt = self.limpar_nome(cand["text"])
            href = cand["href"]

            if self.eh_termo_invalido(txt, href):
                continue

            if txt.upper() == nome_modulo.upper() or txt.upper() == "FACE ID 3.0":
                continue

            tem_link_aula = bool(href and not href.endswith("#") and "javascript:" not in href and "whatsapp" not in href.lower())

            txt_upper = txt.upper()
            txt_limpo = re.sub(r'^\d+[\s\.\-]*', '', txt_upper).strip()

            eh_header_sub = cand["isSubHeader"] and not tem_link_aula
            eh_nome_sub_tipico = any(txt_limpo.startswith(pref) for pref in ["MÉTODO", "METODO", "IPHONE", "BÔNUS", "BONUS", "MÓDULO", "MODULO", "FERRAMENTAS", "OSCILOSCÓPIO"]) and not tem_link_aula

            if (eh_header_sub or eh_nome_sub_tipico) and txt_upper not in nomes_sub_criadas:
                if subcat_atual and len(subcat_atual["aulas"]) > 0:
                    subcategorias.append(subcat_atual)

                nomes_sub_criadas.add(txt_upper)
                subcat_atual = {
                    "num_sub": len(subcategorias) + 1,
                    "titulo_sub": txt,
                    "aulas": []
                }
                vistos_na_sub = set()
            else:
                if not subcat_atual:
                    subcat_atual = {
                        "num_sub": 1,
                        "titulo_sub": "MÉTODO CHIP",
                        "aulas": []
                    }
                    vistos_na_sub = set()

                if txt.upper() == subcat_atual["titulo_sub"].upper():
                    continue

                if txt in vistos_na_sub:
                    continue
                vistos_na_sub.add(txt)

                subcat_atual["aulas"].append({
                    "num_aula": len(subcat_atual["aulas"]) + 1,
                    "titulo": txt,
                    "url": href if tem_link_aula else "",
                    "texto_original": cand["text"]
                })

        if subcat_atual and len(subcat_atual["aulas"]) > 0:
            subcategorias.append(subcat_atual)

        for idx, sub in enumerate(subcategorias, 1):
            sub["num_sub"] = idx

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
                self.concluido.emit(False, "Nenhuma aula válida foi encontrada na página.")
                return

            for modulo in estrutura_curso:
                num_mod_final = 1
                if os.path.exists(self.destino):
                    pastas_existentes = [d for d in os.listdir(self.destino) if os.path.isdir(os.path.join(self.destino, d))]
                    pasta_existente = None
                    max_num = 0
                    for pasta in pastas_existentes:
                        match = re.match(r'^(\d+)\s*-\s*(.+)$', pasta)
                        if match:
                            n = int(match.group(1))
                            nome = match.group(2).strip()
                            if n > max_num:
                                max_num = n
                            if nome.upper() == modulo['titulo_mod'].upper():
                                pasta_existente = pasta
                                num_mod_final = n
                                break
                    if not pasta_existente:
                        num_mod_final = max_num + 1 if max_num > 0 else 1

                nome_pasta_modulo = f"{num_mod_final:02d} - {modulo['titulo_mod']}"
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
                                        if el.is_displayed():
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