"""
===========================================================
PRT Nexus - Theme Colors
Class: ThemeColors
Description: Paleta de cores centralizada da aplicação.
===========================================================
"""

import re

PALETAS = {
    "slate": {
        "PRIMARY": "#0066CC",
        "PRIMARY_LIGHT": "#4EA3FF",
        "PRIMARY_HOVER": "#1A75FF",
        "BACKGROUND": "#1E1E1E",
        "CARD": "#2A2A2A",
        "HOVER": "#2F2F2F",
        "TEXT": "#FFFFFF",
        "TEXT_SECONDARY": "#B0B0B0",
        "BORDER": "#3A3A3A",
        "SIDEBAR_BG": "#111113",
        "SIDEBAR_BORDER": "#222226",
        "SIDEBAR_LOGO_BG": "#1E1E24",
        "SIDEBAR_LOGO_BORDER": "#2D2D35",
        "SIDEBAR_TITLE": "#F4F4F5",
        "SIDEBAR_ACCENT": "#3B82F6",
        "SIDEBAR_MUTED": "#52525B",
        "SIDEBAR_ACTIVE_BG": "#1F1F24",
        "SIDEBAR_TEXT": "#9E9EA9",
        "SIDEBAR_HOVER_BG": "#18181C",
        "SIDEBAR_HOVER_TEXT": "#E4E4E7",
        "INPUT": "#252526",
        "BUTTON_BG": "#2B2B2B",
        "SELECT_BG": "#243044",
    },
    "clean": {
        "PRIMARY": "#1D4ED8",
        "PRIMARY_LIGHT": "#3B82F6",
        "PRIMARY_HOVER": "#1E3A8A",
        "BACKGROUND": "#F3F4F6",
        "CARD": "#FFFFFF",
        "HOVER": "#E5E7EB",
        "TEXT": "#111827",
        "TEXT_SECONDARY": "#6B7280",
        "BORDER": "#D1D5DB",
        "SIDEBAR_BG": "#F8FAFC",
        "SIDEBAR_BORDER": "#E2E8F0",
        "SIDEBAR_LOGO_BG": "#EFF6FF",
        "SIDEBAR_LOGO_BORDER": "#BFDBFE",
        "SIDEBAR_TITLE": "#0F172A",
        "SIDEBAR_ACCENT": "#2563EB",
        "SIDEBAR_MUTED": "#64748B",
        "SIDEBAR_ACTIVE_BG": "#DBEAFE",
        "SIDEBAR_TEXT": "#334155",
        "SIDEBAR_HOVER_BG": "#F1F5F9",
        "SIDEBAR_HOVER_TEXT": "#1E293B",
        "INPUT": "#F9FAFB",
        "BUTTON_BG": "#EEF2FF",
        "SELECT_BG": "#C7D2FE",
    },
    "cyber": {
        "PRIMARY": "#06B6D4",
        "PRIMARY_LIGHT": "#67E8F9",
        "PRIMARY_HOVER": "#0891B2",
        "BACKGROUND": "#07080F",
        "CARD": "#12141C",
        "HOVER": "#1A1E2B",
        "TEXT": "#E7FBFF",
        "TEXT_SECONDARY": "#8BA3B8",
        "BORDER": "#1C4554",
        "SIDEBAR_BG": "#05060A",
        "SIDEBAR_BORDER": "#12323C",
        "SIDEBAR_LOGO_BG": "#0C1218",
        "SIDEBAR_LOGO_BORDER": "#155E75",
        "SIDEBAR_TITLE": "#F0FDFA",
        "SIDEBAR_ACCENT": "#22D3EE",
        "SIDEBAR_MUTED": "#5E7C8A",
        "SIDEBAR_ACTIVE_BG": "#0E1C24",
        "SIDEBAR_TEXT": "#9BD4E0",
        "SIDEBAR_HOVER_BG": "#101820",
        "SIDEBAR_HOVER_TEXT": "#CFFAFE",
        "INPUT": "#0C1018",
        "BUTTON_BG": "#172033",
        "SELECT_BG": "#134E4A",
    },
}

# Cores soltas do tema escuro original, que passam a seguir um papel da paleta.
_ALIASES = {
    "#252526": "INPUT",
    "#2b2b2b": "BUTTON_BG",
    "#333333": "BORDER",
    "#3c3c3c": "BORDER",
    "#888888": "TEXT_SECONDARY",
    "#cccccc": "TEXT_SECONDARY",
    "#1c1c1c": "CARD",
    "#121212": "BACKGROUND",
    "#181818": "CARD",
    "#2c2c2c": "BORDER",
    "#8ea399": "TEXT_SECONDARY",
    "#243044": "SELECT_BG",
    "#323232": "HOVER",
}

TEMAS = (
    ("slate", "🌙", "Tema Escuro", "Slate Dark"),
    ("clean", "☀️", "Tema Claro", "Clean White"),
    ("cyber", "⚡", "Nexus Cyber", "Neon Void"),
)


def _luminancia(cor: str) -> float:
    hexa = cor.lstrip("#")
    vermelho = int(hexa[0:2], 16)
    verde = int(hexa[2:4], 16)
    azul = int(hexa[4:6], 16)
    return (0.2126 * vermelho + 0.7152 * verde + 0.0722 * azul) / 255


def _saturado(cor: str) -> bool:
    hexa = cor.lstrip("#")
    canais = [int(hexa[i:i + 2], 16) for i in (0, 2, 4)]
    maior, menor = max(canais), min(canais)
    if maior == 0:
        return False
    return (maior - menor) / maior > 0.35


def _mapa_troca(origem: dict, destino: dict) -> dict:
    troca = {}
    for papel, antigo in origem.items():
        novo = destino.get(papel)
        if novo and antigo.lower() != novo.lower():
            troca[antigo.lower()] = novo
    ocupadas = {valor.lower() for valor in origem.values()}
    for antigo, papel in _ALIASES.items():
        chave = antigo.lower()
        novo = destino.get(papel)
        if chave not in ocupadas and chave not in troca and novo:
            troca[chave] = novo
    return troca


def _fundo_saturado(bloco: str) -> bool:
    for achado in re.finditer(r"background(?:-color)?\s*:\s*(#[0-9A-Fa-f]{6})", bloco):
        if _saturado(achado.group(1)):
            return True
    return False


def _substituir(texto: str, mapa: dict, proteger_texto_claro: bool) -> str:
    marcadores = {}
    resultado = texto
    for indice, antigo in enumerate(sorted(mapa, key=len, reverse=True)):
        novo = mapa[antigo]
        if proteger_texto_claro and _luminancia(antigo) > 0.72 and _luminancia(novo) < 0.45:
            continue
        marcador = f"@@COR{indice}@@"
        marcadores[marcador] = novo
        resultado = re.sub(re.escape(antigo), marcador, resultado, flags=re.IGNORECASE)
    for marcador, novo in marcadores.items():
        resultado = resultado.replace(marcador, novo)
    return resultado


def _trocar_folha(css: str, mapa: dict, proteger_texto_claro: bool) -> str:
    if not css:
        return css
    if not any(antigo in css.lower() for antigo in mapa):
        return css
    pedacos = css.split("}")
    saida = []
    for pedaco in pedacos:
        proteger = proteger_texto_claro and _fundo_saturado(pedaco)
        saida.append(_substituir(pedaco, mapa, proteger))
    return "}".join(saida)


def repintar(origem: dict, destino: dict) -> None:
    """Troca as cores já pintadas nos widgets pela paleta nova."""
    mapa = _mapa_troca(origem, destino)
    if not mapa:
        return
    proteger = _luminancia(destino.get("TEXT", "#FFFFFF")) < 0.5

    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QApplication

    from theme.stylesheet import get_stylesheet

    app = QApplication.instance()
    if app is None:
        return

    for widget in list(app.allWidgets()):
        folha = widget.styleSheet()
        if not folha:
            continue
        nova = _trocar_folha(folha, mapa, proteger)
        if nova != folha:
            widget.setStyleSheet(nova)

    app.setStyleSheet(get_stylesheet())
    paleta = app.palette()
    paleta.setColor(QPalette.ColorRole.Window, QColor(ThemeColors.BACKGROUND))
    paleta.setColor(QPalette.ColorRole.WindowText, QColor(ThemeColors.TEXT))
    paleta.setColor(QPalette.ColorRole.Base, QColor(ThemeColors.CARD))
    paleta.setColor(QPalette.ColorRole.AlternateBase, QColor(ThemeColors.HOVER))
    paleta.setColor(QPalette.ColorRole.Text, QColor(ThemeColors.TEXT))
    paleta.setColor(QPalette.ColorRole.Button, QColor(ThemeColors.CARD))
    paleta.setColor(QPalette.ColorRole.ButtonText, QColor(ThemeColors.TEXT))
    paleta.setColor(QPalette.ColorRole.Highlight, QColor(ThemeColors.PRIMARY))
    paleta.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(paleta)


class ThemeColors:
    PRIMARY = PALETAS["slate"]["PRIMARY"]
    PRIMARY_LIGHT = PALETAS["slate"]["PRIMARY_LIGHT"]
    PRIMARY_HOVER = PALETAS["slate"]["PRIMARY_HOVER"]
    BACKGROUND = PALETAS["slate"]["BACKGROUND"]
    CARD = PALETAS["slate"]["CARD"]
    HOVER = PALETAS["slate"]["HOVER"]
    TEXT = PALETAS["slate"]["TEXT"]
    TEXT_SECONDARY = PALETAS["slate"]["TEXT_SECONDARY"]
    BORDER = PALETAS["slate"]["BORDER"]
    SUCCESS = "#22C55E"
    WARNING = "#F59E0B"
    ERROR = "#EF4444"
    SIDEBAR_BG = PALETAS["slate"]["SIDEBAR_BG"]
    SIDEBAR_BORDER = PALETAS["slate"]["SIDEBAR_BORDER"]
    SIDEBAR_LOGO_BG = PALETAS["slate"]["SIDEBAR_LOGO_BG"]
    SIDEBAR_LOGO_BORDER = PALETAS["slate"]["SIDEBAR_LOGO_BORDER"]
    SIDEBAR_TITLE = PALETAS["slate"]["SIDEBAR_TITLE"]
    SIDEBAR_ACCENT = PALETAS["slate"]["SIDEBAR_ACCENT"]
    SIDEBAR_MUTED = PALETAS["slate"]["SIDEBAR_MUTED"]
    SIDEBAR_ACTIVE_BG = PALETAS["slate"]["SIDEBAR_ACTIVE_BG"]
    SIDEBAR_TEXT = PALETAS["slate"]["SIDEBAR_TEXT"]
    SIDEBAR_HOVER_BG = PALETAS["slate"]["SIDEBAR_HOVER_BG"]
    SIDEBAR_HOVER_TEXT = PALETAS["slate"]["SIDEBAR_HOVER_TEXT"]
    INPUT = PALETAS["slate"]["INPUT"]
    BUTTON_BG = PALETAS["slate"]["BUTTON_BG"]
    SELECT_BG = PALETAS["slate"]["SELECT_BG"]

    _chave = "slate"

    @classmethod
    def atual(cls) -> str:
        return cls._chave

    @classmethod
    def paleta(cls) -> dict:
        return dict(PALETAS[cls._chave])

    @classmethod
    def aplicar(cls, chave: str) -> None:
        if chave not in PALETAS:
            chave = "slate"
        cls._chave = chave
        for papel, cor in PALETAS[chave].items():
            setattr(cls, papel, cor)
