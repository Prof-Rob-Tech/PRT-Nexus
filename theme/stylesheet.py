"""
===========================================================
PRT Nexus - QSS Stylesheet Generator
Description: Gerador de estilos globais da aplicação.
===========================================================
"""

from theme.colors import ThemeColors


def get_stylesheet() -> str:
    """Retorna a folha de estilo QSS global para aplicação na MainWindow."""
    return f"""
    QMainWindow, QDialog {{
        background-color: {ThemeColors.BACKGROUND};
        color: {ThemeColors.TEXT};
    }}

    QWidget {{
        font-family: 'Segoe UI', system-ui, sans-serif;
        font-size: 13px;
        color: {ThemeColors.TEXT};
    }}

    /* Barram de Rolagem (ScrollBar) */
    QScrollBar:vertical {{
        border: none;
        background: {ThemeColors.BACKGROUND};
        width: 8px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {ThemeColors.BORDER};
        min-height: 20px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {ThemeColors.PRIMARY_LIGHT};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    /* Inputs de Texto */
    QLineEdit, QTextEdit, QPlainTextEdit {{
        background-color: {ThemeColors.CARD};
        border: 1px solid {ThemeColors.BORDER};
        border-radius: 6px;
        padding: 8px 12px;
        color: {ThemeColors.TEXT};
        selection-background-color: {ThemeColors.PRIMARY};
    }}
    QLineEdit:focus, QTextEdit:focus {{
        border: 1px solid {ThemeColors.PRIMARY_LIGHT};
    }}

    /* Botões Padrão */
    QPushButton {{
        background-color: {ThemeColors.CARD};
        border: 1px solid {ThemeColors.BORDER};
        border-radius: 6px;
        padding: 8px 16px;
        color: {ThemeColors.TEXT};
        font-weight: 500;
    }}
    QPushButton:hover {{
        background-color: {ThemeColors.HOVER};
        border-color: {ThemeColors.PRIMARY_LIGHT};
    }}
    QPushButton:pressed {{
        background-color: {ThemeColors.PRIMARY};
    }}

    /* Tooltips */
    QToolTip {{
        background-color: {ThemeColors.CARD};
        color: {ThemeColors.TEXT};
        border: 1px solid {ThemeColors.BORDER};
        border-radius: 4px;
        padding: 4px 8px;
    }}
    """