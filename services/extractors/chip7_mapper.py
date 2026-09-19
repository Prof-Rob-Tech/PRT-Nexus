import re
import time
import unicodedata
from selenium.webdriver.common.by import By


class Chip7Mapper:
    TRECHOS_BLOQUEADOS = [
        "SE ESPECIALIZE", "TREINAMENTOS", "WHATSAPP", "INSTAGRAM", "YOUTUBE",
        "FACEBOOK", "TELEGRAM", "TIKTOK", "CARRINHO", "MINHA CONTA", "MEUS CURSOS",
        "FALE CONOSCO", "ATENDIMENTO", "POLÍTICA DE PRIVACIDADE", "TERMOS DE USO",
        "TODOS OS DIREITOS", "DIREITOS RESERVADOS", "LOGOUT", "SAIR",
        "BEM VINDO", "BEM-VINDO", "DÚVIDAS", "DUVIDAS", "SUPORTE", 
        "CONTATO", "ESQUECEU A SENHA", "ENTRAR", "NOSSOS CURSOS", "OUTROS CURSOS",
        "ÁREA DO ALUNO", "CURSOS EAD", "CURSOS PRESENCIAIS"
    ]

    DOMINIOS_BLOQUEADOS = [
        "instagram.com", "youtube.com", "youtu.be", "facebook.com", 
        "whatsapp.com", "api.whatsapp.com", "wa.me", "t.me", "tiktok.com"
    ]

    URL_PALAVRAS_BLOQUEADAS = [
        "/carrinho", "/login", "/presencial", "/sair", "/conta", "whatsapp", 
        "/logout", "/perfil", "/certificados", "tel:", "mailto:"
    ]

    # Módulos reais do curso
    NOMES_MODULOS = [
        "MÉTODO CHIP",
        "IPHONE X AO 13 PRO MAX",
        "BÔNUS FACE ID"
    ]

    def __init__(self, driver=None):
        self.driver = driver

    @staticmethod
    def normalizar(texto):
        """Remove acentos, espaços e caracteres especiais para comparação segura."""
        if not texto:
            return ""
        nfkd = unicodedata.normalize('NFD', str(texto))
        sem_acento = u"".join([c for c in nfkd if not unicodedata.combining(c)])
        return re.sub(r'[^A-Z0-9]', '', sem_acento.upper())

    @staticmethod
    def limpar_nome(texto, titulo_modulo=""):
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

        return linhas_validas[0]

    def eh_termo_invalido(self, texto, href=""):
        if not texto:
            return True
        txt_upper = texto.upper().strip()
        href_lower = href.lower() if href else ""

        # Nunca bloqueia nomes de módulos conhecidos
        txt_norm = self.normalizar(texto)
        for mod in self.NOMES_MODULOS:
            if txt_norm == self.normalizar(mod):
                return False

        if re.search(r'\(?\d{2}\)?\s*9?[\s\.]?\d{4,5}[-\s\.]?\d{4}', texto):
            return True

        if any(dom in href_lower for dom in self.DOMINIOS_BLOQUEADOS):
            return True
        if any(ign in href_lower for ign in self.URL_PALAVRAS_BLOQUEADAS):
            return True
        if any(trecho in txt_upper for trecho in self.TRECHOS_BLOQUEADOS):
            return True

        return False

    def obter_nome_curso(self, driver=None):
        return "FACE ID 3.0"

    def mapear_curso(self, driver=None):
        if driver:
            self.driver = driver

        time.sleep(2.0)
        nome_curso = "FACE ID 3.0"

        # Varre todos os elementos da barra lateral
        js_script = """
        return (function() {
            let todos = Array.from(document.querySelectorAll('a, div, li, span, h1, h2, h3, h4, h5, h6, p'));
            
            let sidebarItems = todos.filter(el => {
                if (el.closest('header, footer, .video-player, #player, iframe, video')) return false;
                let rect = el.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0 && rect.left < (window.innerWidth * 0.45) && rect.top > 80;
            });

            let extraidos = [];
            let vistos = new Set();

            sidebarItems.forEach(el => {
                let txt = el.innerText ? el.innerText.trim() : '';
                if (!txt || txt.length < 3 || txt.length > 120) return;

                let primeiraLinha = txt.split('\\n')[0].trim();
                if (primeiraLinha.length < 3) return;

                let rect = el.getBoundingClientRect();
                let href = el.getAttribute('href') || el.getAttribute('data-url') || (el.closest('a') ? el.closest('a').getAttribute('href') : '');

                if (!vistos.has(primeiraLinha)) {
                    vistos.add(primeiraLinha);
                    extraidos.push({
                        text: primeiraLinha,
                        href: href || '',
                        top: rect.top,
                        raw: txt
                    });
                }
            });

            extraidos.sort((a, b) => a.top - b.top);
            return extraidos;
        })();
        """

        raw_items = self.driver.execute_script(js_script) or []

        modulos_dict = {}
        modulo_atual = "MÉTODO CHIP"
        vistos_globais = set()

        # Dicionário de módulos normalizados
        modulos_norm = {self.normalizar(m): m for m in self.NOMES_MODULOS}

        for item in raw_items:
            txt_raw = item.get("text", "")
            href = item.get("href", "")
            txt_norm = self.normalizar(txt_raw)

            if txt_norm == self.normalizar(nome_curso):
                continue

            # 1. Verifica se o texto é um dos módulos (insensível a acentos/maiúsculas)
            if txt_norm in modulos_norm:
                modulo_atual = modulos_norm[txt_norm]
                continue

            if self.eh_termo_invalido(txt_raw, href):
                continue

            # 2. Limpa o nome da aula
            aula_limpa = self.limpar_nome(txt_raw, titulo_modulo=modulo_atual)
            if not aula_limpa:
                continue

            if modulo_atual not in modulos_dict:
                modulos_dict[modulo_atual] = []

            chave_aula = f"{modulo_atual}::{aula_limpa}"
            if chave_aula not in vistos_globais:
                vistos_globais.add(chave_aula)
                modulos_dict[modulo_atual].append({
                    "num_aula": len(modulos_dict[modulo_atual]) + 1,
                    "titulo": aula_limpa,
                    "url": href if href and not href.endswith("#") and "javascript:" not in href else "",
                    "texto_original": txt_raw
                })

        estrutura_final = []
        num_mod = 1

        for mod_nome in self.NOMES_MODULOS:
            if mod_nome in modulos_dict and modulos_dict[mod_nome]:
                estrutura_final.append({
                    "nome_curso": nome_curso,
                    "num_mod": num_mod,
                    "titulo_mod": mod_nome,
                    "aulas": modulos_dict[mod_nome]
                })
                num_mod += 1

        return estrutura_final