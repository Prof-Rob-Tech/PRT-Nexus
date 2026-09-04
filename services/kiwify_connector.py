"""
===========================================================
PRT Nexus - Kiwify Connector Service
Class: KiwifyConnector
Description: Lógica para captura e extração de vídeos/aulas do Kiwify.
===========================================================
"""
import re
from typing import Dict, Any, List, Optional


class KiwifyConnector:
    """Serviço responsável por autenticar e extrair conteúdo da Kiwify."""

    def __init__(self, auth_token: Optional[str] = None) -> None:
        self.auth_token = auth_token

    def set_auth_token(self, token: str) -> None:
        """Define o token/cookie de sessão para áreas de membros restritas."""
        self.auth_token = token.strip()

    def validate_url(self, url: str) -> bool:
        """Verifica se a URL informada pertence ao domínio da Kiwify."""
        pattern = r"https?://([a-zA-Z0-9\-]+\.)?kiwify\.com\.br/.*"
        return bool(re.match(pattern, url))

    def fetch_course_info(self, url: str) -> Dict[str, Any]:
        """
        Analisa a URL e retorna as informações básicas da aula ou curso.
        """
        if not self.validate_url(url):
            return {
                "success": False,
                "error": "URL inválida. Insira um link válido da Kiwify (ex: members.kiwify.com.br)."
            }

        # Lógica simulada/preparada para integração HTTP (requests / yt-dlp / Playwright)
        return {
            "success": True,
            "title": "Aula Kiwify Capturada",
            "url": url,
            "modules": [
                {
                    "module_name": "Módulo 1 - Introdução",
                    "lessons": [
                        {"title": "01. Boas-vindas ao Curso", "type": "video", "status": "Ready"},
                        {"title": "02. Visão Geral da Plataforma", "type": "video", "status": "Ready"}
                    ]
                }
            ]
        }

class KiwifyConnector:
    """Serviço responsável por extrair módulos e estruturar pastas de download."""

    def __init__(self, auth_token: Optional[str] = None) -> None:
        self.auth_token = auth_token

    def format_download_queue(self, course_title: str, modules: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """
        Mapeia a estrutura do curso para itens de download com pasta de destino.
        Exemplo: subfolder = "Kiwify/DIA 01"
        """
        queue_items = []
        for module in modules:
            module_name = module.get("module_name", "Geral")
            for lesson in module.get("lessons", []):
                queue_items.append({
                    "title": lesson.get("title"),
                    "url": lesson.get("url", ""),
                    "subfolder": f"{course_title}/{module_name}",
                    "status": "Pendente"
                })
        return queue_items