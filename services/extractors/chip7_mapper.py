import re
import time
from selenium.webdriver.common.by import By


class Chip7Mapper:
    TRECHOS_BLOQUEADOS = [
        "SE ESPECIALIZE", "TREINAMENTOS", "WHATSAPP", "INSTAGRAM", "YOUTUBE",
        "FACEBOOK", "TELEGRAM", "TIKTOK", "CARRINHO", "MINHA CONTA", "MEUS CURSOS",
        "FALE CONOSCO", "ATENDIMENTO", "POLÍTICA DE PRIVACIDADE", "TERMOS DE USO",
        "TODOS OS DIREITOS", "DIREITOS RESERVADOS", "LOGOUT", "SAIR",
        "BEM VINDO", "BEM-VINDO", "DÚVIDAS", "DUVIDAS", "SUPORTE", 
        "CONTATO", "ESQUECEU A SENHA", "ENTRAR", "NOSSOS CURSOS", "OUTROS CURSOS"
    ]

    DOMINIOS_BLOQUEADOS = [
        "instagram.com", "youtube.com", "youtu.be", "facebook.com", 
        "whatsapp.com", "api.whatsapp.com", "wa.me", "t.me", "tiktok.com"
    ]

    URL_PALAVRAS_BLOQUEADAS = [
        "/carrinho", "/login", "/presencial", "/sair", "/conta", "whatsapp", 
        "/logout", "/perfil", "/certificados", "tel:", "mailto:"
    ]

    def __init__(self, driver=None):
        self.driver = driver

    @staticmethod
    def limpar_nome(texto, titulo_modulo=""):
        """Método exigido pelo gerenciador de downloads para higienizar nomes de arquivos."""
        if not texto:
            return ""

        linhas = [l.strip() for l in re.split(r'[\n|]', str(texto)) if l.strip()]
        linhas_validas = []

        for l in linhas:
            l_clean = re.sub(r'\b(Concluído|Concluido|Assistido|Pendente)\b', '', l, flags=re.IGNORECASE).strip()
            l_clean = re.sub(r'\b\d{1,2}:\d{2}(?::\d{2})?\b', '', l_clean).strip()
            l_clean = re.sub(r'\.mp4$', '', l_clean, flags=re.IGNORECASE).strip()
            l_clean = re.sub(r'[\\/*?:"<>|]', '', l_clean).strip()
            
            if len(l_clean) >= 3 and not re.match(r'^\d+%$', l_clean):
                linhas_validas.append(l_clean)

        if not linhas_validas:
            return ""

        if len(linhas_validas) > 1 and titulo_modulo:
            for l in linhas_validas:
                if l.upper() != titulo_modulo.upper():
                    return l

        return linhas_validas[-1]

    @staticmethod
    def extrair_partes(texto):
        """Separa o texto bruto do card em (titulo_modulo, titulo_aula)."""
        if not texto:
            return "", ""

        linhas_raw = [l.strip() for l in re.split(r'[\n|]', str(texto)) if l.strip()]
        linhas_limpas = []

        for l in linhas_raw:
            l_clean = re.sub(r'\b(Concluído|Concluido|Assistido|Pendente)\b', '', l, flags=re.IGNORECASE).strip()
            l_clean = re.sub(r'\b\d{1,2}:\d{2}(?::\d{2})?\b', '', l_clean).strip()
            l_clean = re.sub(r'\.mp4$', '', l_clean, flags=re.IGNORECASE).strip()
            l_clean = re.sub(r'[\\/*?:"<>|]', '', l_clean).strip()
            
            if len(l_clean) >= 3 and not re.match(r'^\d+%$', l_clean):
                linhas_limpas.append(l_clean)

        if not linhas_limpas:
            return "", ""

        if len(linhas_limpas) == 1:
            return "", linhas_limpas[0]

        mod_title = linhas_limpas[0]
        aula_title = linhas_limpas[-1]

        if mod_title.upper() == aula_title.upper():
            return "", aula_title

        return mod_title, aula_title

    def eh_termo_invalido(self, texto, href=""):
        if not texto:
            return True
        txt_upper = texto.upper().strip()
        href_lower = href.lower() if href else ""

        if re.search(r'\(?\d{2}\)?\s*9?[\s\.]?\d{4,5}[-\s\.]?\d{4}', texto):
            return True

        if any(dom in href_lower for dom in self.DOMINIOS_BLOQUEADOS):
            return True
        if any(ign in href_lower for ign in self.URL_PALAVRAS_BLOQUEADAS):
            return True
        if any(trecho in txt_upper for trecho in self.TRECHOS_BLOQUEADOS):
            return True

        return False

    def mapear_curso(self, driver=None):
        if driver:
            self.driver = driver

        time.sleep(1.5)

        js_script = """
        return (function() {
            let grid = document.querySelector('.student-course-grid') || document.querySelector('.student-course-layout') || document.body;
            let elementos = Array.from(grid.querySelectorAll('li, a, div[class*="lesson"], div[class*="aula"]'));

            let itens = [];
            elementos.forEach(el => {
                if (el.closest('footer, header, nav')) return;
                let txt = el.innerText ? el.innerText.trim() : '';
                let href = el.getAttribute('href') || el.getAttribute('data-url') || '';
                if (txt.length >= 3) {
                    itens.push({ text: txt, href: href });
                }
            });

            return itens;
        })();
        """

        raw_items = self.driver.execute_script(js_script) or []
        
        modulos_dict = {}
        modulo_atual_nome = "MÉTODO CHIP"
        vistos_globais = set()

        for item in raw_items:
            txt_raw = item.get("text", "")
            href = item.get("href", "")

            mod_ext, aula_ext = self.extrair_partes(txt_raw)

            if not aula_ext or self.eh_termo_invalido(aula_ext, href):
                continue

            if mod_ext and not self.eh_termo_invalido(mod_ext):
                modulo_atual_nome = mod_ext

            if modulo_atual_nome not in modulos_dict:
                modulos_dict[modulo_atual_nome] = []

            chave_aula = f"{modulo_atual_nome}::{aula_ext}"
            if chave_aula not in vistos_globais:
                vistos_globais.add(chave_aula)
                modulos_dict[modulo_atual_nome].append({
                    "num_aula": len(modulos_dict[modulo_atual_nome]) + 1,
                    "titulo": aula_ext,
                    "url": href if href and not href.endswith("#") and "javascript:" not in href else "",
                    "texto_original": txt_raw
                })

        estrutura_final = []
        num_mod = 1

        for mod_nome, aulas in modulos_dict.items():
            if aulas:
                estrutura_final.append({
                    "nome_curso": "FACE ID 3.0",
                    "num_mod": num_mod,
                    "titulo_mod": mod_nome,
                    "aulas": aulas
                })
                num_mod += 1

        return estrutura_final