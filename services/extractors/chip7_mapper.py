import re
import time
from selenium.webdriver.common.by import By


class Chip7Mapper:
    TRECHOS_BLOQUEADOS = [
        "SE ESPECIALIZE", "TREINAMENTOS", "WHATSAPP", "INSTAGRAM", "YOUTUBE",
        "FACEBOOK", "TELEGRAM", "TIKTOK", "CARRINHO", "MINHA CONTA",
        "MEUS CURSOS", "ÁREA DO ALUNO", "AREA DO ALUNO", "FALE CONOSCO",
        "ATENDIMENTO", "POLÍTICA DE PRIVACIDADE", "TERMOS DE USO",
        "TODOS OS DIREITOS", "DIREITOS RESERVADOS", "LOGOUT", "SAIR",
        "BEM VINDO", "BEM-VINDO", "CURSOS EAD", "CURSOS PRESENCIAIS",
        "MEUS CERTIFICADOS", "DÚVIDAS", "DUVIDAS", "MEU PERFIL", "CONCLUÍDO", "CONCLUIDO"
    ]

    SECOES_CATEGORIAS = [
        "MÉTODO CHIP", "METODO CHIP", "BÔNUS FACE ID", "BONUS FACE ID",
        "FACE ID 3.0"
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

    @staticmethod
    def limpar_nome(texto):
        if not texto:
            return ""
        # Remove extensão .mp4 se houver
        texto = re.sub(r'\.mp4$', '', texto, flags=re.IGNORECASE)
        # Remove marcas de duração (ex: 10:15 ou 01:23:45) e status da interface
        texto = re.sub(r'\b\d{1,2}:\d{2}(?::\d{2})?\b', '', texto)
        texto = re.sub(r'\b(Concluído|Concluido|Assistido|Pendente)\b', '', texto, flags=re.IGNORECASE)
        # Remove caracteres proibidos em caminhos do sistema operacional
        texto = re.sub(r'[\\/*?:"<>|]', '', texto)
        # Normaliza múltiplos espaços
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
        if txt_upper in self.SECOES_CATEGORIAS:
            return True

        return False

    def expandir_modulos(self):
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

        js_script = """
        return (function() {
            let items = [];
            let rawElements = document.querySelectorAll('aside *, .sidebar *, [class*="sidebar"] *, [class*="menu"] *, [class*="playlist"] *, [class*="aula"] *, [class*="lesson"] *, a, li, p, span, div');
            let widthThreshold = window.innerWidth * 0.38;

            rawElements.forEach(el => {
                let rect = el.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0 || rect.top < 130 || rect.left > widthThreshold) {
                    return;
                }

                let children = Array.from(el.children);
                let temFilhoComTexto = children.some(c => {
                    let r = c.getBoundingClientRect();
                    let t = c.innerText ? c.innerText.trim() : '';
                    return r.width > 0 && r.height > 0 && t.length > 0 && 
                           ['DIV', 'A', 'LI', 'UL', 'P', 'H1', 'H2', 'H3', 'H4', 'H5', 'SECTION', 'NAV'].includes(c.tagName);
                });

                if (temFilhoComTexto) return;

                let txt = el.innerText ? el.innerText.trim() : '';
                if (!txt) return;

                txt = txt.replace(/\\s+/g, ' ');

                if (txt.length >= 3 && txt.length <= 120) {
                    let href = el.getAttribute('href') || (el.tagName === 'A' ? el.href : '');
                    items.push({
                        text: txt,
                        href: href || '',
                        tag: el.tagName
                    });
                }
            });
            return items;
        })();
        """

        candidatos_js = self.driver.execute_script(js_script) or []

        aulas = []
        vistos = set()

        for cand in candidatos_js:
            txt = self.limpar_nome(cand["text"])
            href = cand["href"]

            if len(txt) < 3 or len(txt) > 150:
                continue

            if self.eh_termo_invalido(txt, href):
                continue

            txt_upper = txt.upper()
            if txt_upper == nome_modulo.upper():
                continue

            if txt not in vistos:
                vistos.add(txt)
                aulas.append({
                    "num_aula": len(aulas) + 1,
                    "titulo": txt,
                    "url": href if href and not href.endswith("#") and "javascript:" not in href else "",
                    "texto_original": cand["text"]
                })

        return [{
            "num_mod": 1,
            "titulo_mod": nome_modulo,
            "aulas": aulas
        }]