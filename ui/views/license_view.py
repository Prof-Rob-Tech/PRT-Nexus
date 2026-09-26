"""
===========================================================
PRT Nexus - License View
Class: LicenseView
Description: Aparência da tela de licença e planos.
             A validação da chave entra depois.
===========================================================
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from theme.colors import ThemeColors

_PLANOS = (
    {
        "nome": "PRT STARTER",
        "preco": "R$ 47",
        "periodo": "/mês",
        "cor": "#22C55E",
        "destaque": False,
        "itens": (
            "1 Conexão Simultânea",
            "Downloads até 1080p",
            "Suporte Comunitário",
        ),
    },
    {
        "nome": "PRT PRO",
        "preco": "R$ 97",
        "periodo": "/mês",
        "cor": "#A78BFA",
        "destaque": True,
        "itens": (
            "3 Conexões Simultâneas",
            "Downloads 4K Ultra HD",
            "Sniffer Avançado HLS/M3U8",
        ),
    },
    {
        "nome": "PRT ENTERPRISE",
        "preco": "R$ 297",
        "periodo": "/único",
        "cor": "#60A5FA",
        "destaque": False,
        "itens": (
            "Conexões Ilimitadas",
            "Todas as funções PRO liberadas",
            "Atualizações Vitalícias",
        ),
    },
)

_RESUMO = (
    ("CHAVE DE LICENÇA", "PRT-9988-XXXX-7711"),
    ("HARDWARE ID (HWID)", "HWID-A8R-2-9MC1-4BD2"),
    ("EXPIRA EM", "Nunca (Acesso Vitalício)"),
    ("CONEXÕES SIMULTÂNEAS", "Unlimited / Ilimitado"),
)


class LicenseView(QWidget):
    """Tela visual de licença. A ativação ainda não consulta chave nenhuma."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("licenseView")
        self._cartoes: list[QFrame] = []
        self._rotulos: list[tuple[QLabel, str]] = []
        self._caixas: list[QFrame] = []
        self._valores: list[QLabel] = []
        self._planos: list[QFrame] = []
        self._montar()
        self.pintar()

    def _rotulo(self, texto: str, papel: str) -> QLabel:
        rotulo = QLabel(texto)
        self._rotulos.append((rotulo, papel))
        return rotulo

    def _montar(self) -> None:
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")
        self._scroll = scroll

        pagina = QWidget()
        pagina.setObjectName("licensePage")
        self._pagina = pagina
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        layout.addWidget(self._rotulo("🔑  Minha Licença & Planos", "titulo"))
        layout.addWidget(self._rotulo(
            "Gerencie seu plano ativo, chave de licença, HWID e opções de renovação.",
            "subtitulo",
        ))

        cartao = QFrame()
        self._cartoes.append(cartao)
        cartao_layout = QVBoxLayout(cartao)
        cartao_layout.setContentsMargins(16, 14, 16, 14)
        cartao_layout.setSpacing(12)

        topo = QHBoxLayout()
        topo.addWidget(self._rotulo("🔑  PRT NEXUS PRO - VITALÍCIO", "plano_ativo"), stretch=1)
        topo.addWidget(self._rotulo("● ATIVO", "ativo"))
        cartao_layout.addLayout(topo)

        linha = QHBoxLayout()
        linha.setSpacing(10)
        for titulo, valor in _RESUMO:
            bloco = QFrame()
            self._caixas.append(bloco)
            bloco_layout = QVBoxLayout(bloco)
            bloco_layout.setContentsMargins(10, 8, 10, 8)
            bloco_layout.setSpacing(4)
            bloco_layout.addWidget(self._rotulo(titulo, "campo"))
            lbl_valor = self._rotulo(valor, "valor")
            self._valores.append(lbl_valor)
            bloco_layout.addWidget(lbl_valor)
            linha.addWidget(bloco, stretch=1)
        cartao_layout.addLayout(linha)
        layout.addWidget(cartao)

        layout.addWidget(self._rotulo("⚡  Ativar ou Renovar Licença", "secao"))
        ativar = QHBoxLayout()
        ativar.setSpacing(10)
        self.campo_chave = QLineEdit()
        self.campo_chave.setPlaceholderText("Insira sua chave de licença (Ex: PRT-NEXUS-XXXX-XXXX-XXXX)")
        self.campo_chave.setFixedHeight(36)
        self.btn_validar = QPushButton("Validar e Ativar Key")
        self.btn_validar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_validar.setFixedHeight(36)
        ativar.addWidget(self.campo_chave, stretch=1)
        ativar.addWidget(self.btn_validar)
        layout.addLayout(ativar)

        layout.addWidget(self._rotulo("💎  Conheça os Planos PRT NEXUS", "secao"))
        planos = QHBoxLayout()
        planos.setSpacing(12)
        for plano in _PLANOS:
            card = self._card_plano(plano)
            self._planos.append(card)
            planos.addWidget(card, stretch=1)
        layout.addLayout(planos)
        layout.addStretch()

        scroll.setWidget(pagina)
        raiz.addWidget(scroll)

    def _card_plano(self, plano: dict) -> QFrame:
        card = QFrame()
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        caixa = QVBoxLayout(card)
        caixa.setContentsMargins(16, 16, 16, 16)
        caixa.setSpacing(8)
        caixa.addWidget(self._rotulo(plano["nome"], "nome_plano"))

        preco = QHBoxLayout()
        preco.setSpacing(4)
        lbl_preco = QLabel(plano["preco"])
        lbl_preco.setStyleSheet(f"color: {plano['cor']}; font-size: 22px; font-weight: 800; background: transparent; border: none;")
        lbl_periodo = self._rotulo(plano["periodo"], "periodo")
        preco.addWidget(lbl_preco)
        preco.addWidget(lbl_periodo, alignment=Qt.AlignmentFlag.AlignBottom)
        preco.addStretch()
        caixa.addLayout(preco)

        for item in plano["itens"]:
            linha = QHBoxLayout()
            linha.setSpacing(6)
            marca = QLabel("✓")
            marca.setStyleSheet("color: #22C55E; font-size: 13px; font-weight: 700; background: transparent; border: none;")
            marca.setFixedWidth(14)
            linha.addWidget(marca)
            linha.addWidget(self._rotulo(item, "item"), stretch=1)
            caixa.addLayout(linha)
        caixa.addStretch()
        return card

    def pintar(self) -> None:
        self.setStyleSheet(
            f"QWidget#licenseView {{ background-color: {ThemeColors.BACKGROUND}; }}"
        )
        self._pagina.setStyleSheet(
            f"QWidget#licensePage {{ background-color: {ThemeColors.BACKGROUND}; }}"
        )
        estilos = {
            "titulo": f"font-size: 20px; font-weight: bold; color: {ThemeColors.TEXT}; background: transparent; border: none;",
            "subtitulo": f"font-size: 13px; color: {ThemeColors.TEXT_SECONDARY}; background: transparent; border: none;",
            "secao": f"font-size: 14px; font-weight: 700; color: {ThemeColors.TEXT}; background: transparent; border: none;",
            "plano_ativo": f"font-size: 13px; font-weight: 700; color: {ThemeColors.TEXT}; background: transparent; border: none;",
            "ativo": "font-size: 11px; font-weight: 800; color: #22C55E; background: transparent; border: none;",
            "campo": f"font-size: 10px; font-weight: 700; color: {ThemeColors.TEXT_SECONDARY}; background: transparent; border: none; letter-spacing: 0.3px;",
            "valor": f"font-size: 12px; font-weight: 600; color: {ThemeColors.TEXT}; background: transparent; border: none;",
            "nome_plano": f"font-size: 12px; font-weight: 800; color: {ThemeColors.TEXT_SECONDARY}; background: transparent; border: none; letter-spacing: 0.4px;",
            "periodo": f"font-size: 12px; color: {ThemeColors.TEXT_SECONDARY}; background: transparent; border: none;",
            "item": f"font-size: 13px; color: {ThemeColors.TEXT}; background: transparent; border: none;",
        }
        for rotulo, papel in self._rotulos:
            rotulo.setStyleSheet(estilos[papel])

        for cartao in self._cartoes:
            cartao.setStyleSheet(
                f"QFrame {{ background-color: {ThemeColors.CARD}; border: 1px solid {ThemeColors.BORDER}; border-radius: 8px; }}"
            )
        for caixa in self._caixas:
            caixa.setStyleSheet(
                f"QFrame {{ background-color: {ThemeColors.BACKGROUND}; border: 1px solid {ThemeColors.BORDER}; border-radius: 6px; }}"
            )
        self.campo_chave.setStyleSheet(f"""
            QLineEdit {{
                background-color: {ThemeColors.CARD};
                color: {ThemeColors.TEXT};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
                padding: 0 12px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {ThemeColors.PRIMARY};
            }}
        """)
        self.btn_validar.setStyleSheet(f"""
            QPushButton {{
                background-color: {ThemeColors.CARD};
                color: {ThemeColors.TEXT};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
                padding: 0 16px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {ThemeColors.PRIMARY_LIGHT};
            }}
        """)
        for indice, card in enumerate(self._planos):
            destaque = _PLANOS[indice]["destaque"]
            borda = f"2px solid {ThemeColors.PRIMARY}" if destaque else f"1px solid {ThemeColors.BORDER}"
            card.setStyleSheet(
                f"QFrame {{ background-color: {ThemeColors.CARD}; border: {borda}; border-radius: 8px; }}"
            )
