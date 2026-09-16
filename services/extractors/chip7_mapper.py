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
        "MEUS CERTIFICADOS", "DÚVIDAS", "DUVIDAS", "MEU PERFIL", "CONCLUÍDO", "CONCLUIDO",
        "SUPORTE", "CONTATO", "CHALAT"
    ]

    SECOES_CATEGORIAS = []

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

        # Regex flexibilizado para capturar telefones com pontos (ex: (48) 9.9908-7359)
        if re.search(r'\(?\d{2}\)?\s*9?[\s\.]?\d{4,5}[-\s\.]?\d{4}', texto):
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

    def _mapear_aulas_planas(self):
        """Mapeamento secundário ignorando rodapés e elementos de suporte."""
        js_script = """
        return Array.from(document.querySelectorAll('a, li, span, div[class*="aula"], div[class*="lesson"]'))
            .filter(el => !el.closest('footer, .footer, #footer, .suporte, #suporte, .whatsapp'))
            .map(el => ({
                text: el.innerText ? el.innerText.trim() : '',
                href: el.getAttribute('href') || ''
            }));
        """
        itens = self.driver.execute_script(js_script) or []
        aulas = []
        vistos = set()

        for item in itens:
            txt = self.limpar_nome(item.get("text", ""))
            href = item.get("href", "")

            if len(txt) < 3 or len(txt) > 150 or self.eh_termo_invalido(txt, href):
                continue

            if txt not in vistos:
                vistos.add(txt)
                aulas.append({
                    "num_aula": len(aulas) + 1,
                    "titulo": txt,
                    "url": href if href and not href.endswith("#") and "javascript:" not in href else "",
                    "texto_original": item.get("text", "")
                })
        return aulas

    def mapear_curso(self, driver=None):
        if driver:
            self.driver = driver

        self.expandir_modulos()
        time.sleep(2)

        nome_curso = self.extrair_nome_modulo()

        js_script = """
        return (function() {
            let modulos = [];
            let accordions = document.querySelectorAll('.card, .accordion-item, .modulo, [class*="modulo"]');
            
            if (accordions.length === 0) {
                return [{ titulo: "", itens: [] }];
            }

            accordions.forEach((acc, idx) => {
                let header = acc.querySelector('.card-header, .accordion-header, h2, h3, h4, .title');
                let tituloMod = header ? header.innerText.trim() : `Módulo ${idx + 1}`;
                let links = Array.from(acc.querySelectorAll('a, li, span'))
                    .filter(el => !el.closest('footer, .footer, #footer, .suporte, #suporte, .whatsapp'))
                    .map(el => ({
                        text: el.innerText ? el.innerText.trim() : '',
                        href: el.getAttribute('href') || ''
                    }));
                modulos.push({ titulo: tituloMod, itens: links });
            });
            return modulos;
        })();
        """

        dados_modulos = self.driver.execute_script(js_script) or []
        
        estrutura_final = []
        num_mod = 1

        for mod in dados_modulos:
            titulo_mod_limpo = self.limpar_nome(mod.get("titulo", ""))
            if not titulo_mod_limpo or self.eh_termo_invalido(titulo_mod_limpo):
                titulo_mod_limpo = f"Módulo {num_mod}"

            aulas = []
            vistos = set()

            for item in mod.get("itens", []):
                txt = self.limpar_nome(item.get("text", ""))
                href = item.get("href", "")

                if len(txt) < 3 or len(txt) > 150 or self.eh_termo_invalido(txt, href):
                    continue

                if txt not in vistos and txt.upper() != titulo_mod_limpo.upper():
                    vistos.add(txt)
                    aulas.append({
                        "num_aula": len(aulas) + 1,
                        "titulo": txt,
                        "url": href if href and not href.endswith("#") and "javascript:" not in href else "",
                        "texto_original": item.get("text", "")
                    })

            if aulas:
                estrutura_final.append({
                    "nome_curso": nome_curso,
                    "num_mod": num_mod,
                    "titulo_mod": titulo_mod_limpo,
                    "aulas": aulas
                })
                num_mod += 1

        if not estrutura_final:
            aulas_gerais = self._mapear_aulas_planas()
            if aulas_gerais:
                estrutura_final.append({
                    "nome_curso": nome_curso,
                    "num_mod": 1,
                    "titulo_mod": "MÉTODO CHIP",
                    "aulas": aulas_gerais
                })

        return estrutura_final