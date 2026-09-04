"""
===========================================================
PRT Nexus - Font Configurations
Class: ThemeFonts
Description: Definição de fontes padrão do PySide6.
===========================================================
"""

from PySide6.QtGui import QFont


class ThemeFonts:
    FAMILY = "Segoe UI"

    @classmethod
    def regular(cls, size: int = 13) -> QFont:
        return QFont(cls.FAMILY, size, QFont.Weight.Normal)

    @classmethod
    def bold(cls, size: int = 13) -> QFont:
        return QFont(cls.FAMILY, size, QFont.Weight.Bold)