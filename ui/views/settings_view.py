"""
===========================================================
PRT Nexus - Settings View
Class: SettingsView
Description: Aparência do aplicativo e comportamento ao fechar.
===========================================================
"""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from theme.colors import PALETAS, TEMAS, ThemeColors, repintar

try:
    from database.manager import db_manager
except ImportError:
    db_manager = None

_ICONE_CHECK = (Path(__file__).resolve().parents[2] / "theme" / "check.svg").as_posix()


class SettingsView(QWidget):
    """Escolha de tema e opção de continuar na bandeja."""

    tema_mudou = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("settingsView")
        self._botoes: dict[str, QPushButton] = {}
        self._montar()
        self.pintar()

    def _montar(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        self.lbl_titulo = QLabel("⚙️  Configurações do Sistema")
        layout.addWidget(self.lbl_titulo)

        self.lbl_aparencia = QLabel("APARÊNCIA E PERSONALIZAÇÃO")
        layout.addWidget(self.lbl_aparencia)

        linha = QHBoxLayout()
        linha.setSpacing(12)
        for chave, icone, nome, apelido in TEMAS:
            botao = QPushButton(f"{icone}\n{nome}\n({apelido})")
            botao.setCursor(Qt.CursorShape.PointingHandCursor)
            botao.setMinimumHeight(78)
            botao.clicked.connect(lambda _, c=chave: self.escolher_tema(c))
            self._botoes[chave] = botao
            linha.addWidget(botao, stretch=1)
        layout.addLayout(linha)

        self.caixa = QFrame()
        caixa_layout = QVBoxLayout(self.caixa)
        caixa_layout.setContentsMargins(14, 12, 14, 12)
        caixa_layout.setSpacing(8)

        self.lbl_comportamento = QLabel("COMPORTAMENTO DO APLICATIVO")
        caixa_layout.addWidget(self.lbl_comportamento)

        self.chk_bandeja = QCheckBox("Manter aplicativo rodando na bandeja do sistema ao fechar (X)")
        self.chk_bandeja.setCursor(Qt.CursorShape.PointingHandCursor)
        if db_manager is not None:
            self.chk_bandeja.setChecked(db_manager.get_setting("bandeja", "0") == "1")
        self.chk_bandeja.toggled.connect(self._salvar_bandeja)
        caixa_layout.addWidget(self.chk_bandeja)
        layout.addWidget(self.caixa)
        layout.addStretch()

    def escolher_tema(self, chave: str) -> None:
        if chave not in PALETAS or chave == ThemeColors.atual():
            self.pintar()
            return
        anterior = ThemeColors.paleta()
        ThemeColors.aplicar(chave)
        if db_manager is not None:
            db_manager.set_setting("tema", chave)
        repintar(anterior, ThemeColors.paleta())
        self.pintar()
        self.tema_mudou.emit()

    def _salvar_bandeja(self, ativo: bool) -> None:
        if db_manager is not None:
            db_manager.set_setting("bandeja", "1" if ativo else "0")

    def pintar(self) -> None:
        self.setStyleSheet(
            f"QWidget#settingsView {{ background-color: {ThemeColors.BACKGROUND}; }}"
        )
        self.lbl_titulo.setStyleSheet(
            f"font-size: 20px; font-weight: bold; color: {ThemeColors.TEXT}; background: transparent; border: none;"
        )
        self.lbl_aparencia.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {ThemeColors.TEXT_SECONDARY}; "
            "background: transparent; border: none; letter-spacing: 0.4px;"
        )
        self.lbl_comportamento.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {ThemeColors.TEXT_SECONDARY}; "
            "background: transparent; border: none; letter-spacing: 0.4px;"
        )
        self.caixa.setStyleSheet(
            f"QFrame {{ background-color: {ThemeColors.CARD}; border: 1px solid {ThemeColors.BORDER}; border-radius: 8px; }}"
        )
        self.chk_bandeja.setStyleSheet(f"""
            QCheckBox {{
                color: {ThemeColors.TEXT};
                background: transparent;
                font-size: 13px;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 3px;
                background-color: {ThemeColors.BACKGROUND};
            }}
            QCheckBox::indicator:hover {{
                border-color: {ThemeColors.PRIMARY_LIGHT};
            }}
            QCheckBox::indicator:checked {{
                background-color: {ThemeColors.PRIMARY};
                border: 1px solid {ThemeColors.PRIMARY};
                image: url({_ICONE_CHECK});
            }}
        """)
        ativo = ThemeColors.atual()
        for chave, botao in self._botoes.items():
            if chave == ativo:
                botao.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {ThemeColors.SIDEBAR_ACTIVE_BG};
                        color: {ThemeColors.TEXT};
                        border: 2px solid {ThemeColors.PRIMARY};
                        border-radius: 8px;
                        padding: 10px 8px;
                        font-size: 13px;
                        font-weight: 700;
                    }}
                """)
            else:
                botao.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {ThemeColors.CARD};
                        color: {ThemeColors.TEXT};
                        border: 1px solid {ThemeColors.BORDER};
                        border-radius: 8px;
                        padding: 10px 8px;
                        font-size: 13px;
                        font-weight: 600;
                    }}
                    QPushButton:hover {{
                        border-color: {ThemeColors.PRIMARY_LIGHT};
                    }}
                """)
