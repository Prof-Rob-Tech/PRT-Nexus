"""
===========================================================
PRT Nexus - UI Router
Class: Router
Description: Roteamento central das visões da aplicação.
===========================================================
"""

from PySide6.QtWidgets import QStackedWidget, QWidget
from ui.views.tiktok_view import TikTokView


class Router(QStackedWidget):
    """Gerencia a troca de telas no container principal."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.routes: dict[str, QWidget] = {}

    def register_route(self, name: str, widget: QWidget) -> None:
        """Registra uma rota e adiciona a view ao QStackedWidget."""
        self.routes[name] = widget
        self.addWidget(widget)

    def navigate_to(self, name: str) -> None:
        """Alterna a exibição para a rota desejada."""
        if name in self.routes:
            self.setCurrentWidget(self.routes[name])