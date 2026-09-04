"""
===========================================================
PRT Nexus - Universo Técnico Mapper Service
Description: Autenticação e extração da árvore de cursos/módulos/aulas.
===========================================================
"""

import os
import re
import requests
from bs4 import BeautifulSoup


def sanitize_filename(name: str) -> str:
    """Remove caracteres inválidos do Windows para pastas e arquivos."""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()


class UniversoService:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

    def login(self, email: str, password: str) -> bool:
        """Realiza login no WordPress/WooCommerce do Universo Técnico."""
        login_url = "https://universotecnico.com/wp-login.php"
        payload = {
            "log": email,
            "pwd": password,
            "rememberme": "forever",
            "wp-submit": "Acessar"
        }
        
        try:
            res = self.session.post(login_url, data=payload, timeout=15)
            # Se não houver erro de login nos cookies/resposta
            return res.status_code == 200 and ("wordpress_logged_in" in str(self.session.cookies) or res.url != login_url)
        except Exception:
            return False

    def extract_course_tree(self, course_url: str) -> dict:
        """
        Raspagem da página do curso:
        - Nome do Curso (Pasta Principal)
        - Módulos (Subpastas em Amarelo)
        - Aulas (Ficheiros em Vermelho)
        """
        response = self.session.get(course_url, timeout=15)
        if response.status_code != 200:
            raise Exception(f"Não foi possível acessar a página do curso (HTTP {response.status_code}).")

        soup = BeautifulSoup(response.text, "html.parser")

        # 1. Nome do Curso
        title_el = soup.find("h1") or soup.find("title")
        raw_course_title = title_el.get_text(strip=True) if title_el else "Curso Universo Tecnico"
        course_title = sanitize_filename(raw_course_title)

        modules_tree = []

        # 2. Localiza os contêineres de Módulos (Accordion/Seções)
        module_elements = soup.select(".elementor-accordion-item, .tu-accordion-item, div[class*='accordion'], div[class*='modulo']")
        
        if not module_elements:
            module_elements = soup.find_all("div", class_=lambda c: c and ("accordion" in c or "module" in c))

        mod_index = 1
        for mod_el in module_elements:
            header_el = mod_el.find(["h2", "h3", "h4", "button", "span", "a"])
            if not header_el:
                continue

            mod_title = header_el.get_text(strip=True)
            mod_title = re.sub(r'CONCLUÍDO|CONCLUIDO', '', mod_title, flags=re.IGNORECASE).strip()

            if not mod_title or len(mod_title) < 2:
                continue

            # 3. Aulas pertencentes a este Módulo
            lesson_links = mod_el.find_all("a", href=True)
            lessons = []
            less_index = 1

            for link in lesson_links:
                less_title = link.get_text(strip=True)
                less_url = link["href"]

                if less_title and less_url and less_url != "#" and "javascript" not in less_url:
                    if less_url.startswith("/"):
                        less_url = "https://universotecnico.com" + less_url

                    lessons.append({
                        "index": str(less_index).zfill(2),
                        "title": sanitize_filename(less_title),
                        "url": less_url
                    })
                    less_index += 1

            if lessons:
                modules_tree.append({
                    "index": str(mod_index).zfill(2),
                    "title": sanitize_filename(mod_title),
                    "lessons": lessons
                })
                mod_index += 1

        return {
            "course_title": course_title,
            "modules": modules_tree
        }