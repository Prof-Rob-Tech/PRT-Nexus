"""
===========================================================
PRT Nexus - Database Models
Description: Modelos de dados fortemente tipados.
===========================================================
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class DownloadItem:
    task_id: str
    title: str
    url: str
    platform: str
    file_path: str = ""
    file_size: str = ""
    status: str = "Concluído"
    id: Optional[int] = None
    created_at: Optional[str] = None


@dataclass
class FavoriteItem:
    title: str
    url: str
    platform: str = "geral"
    id: Optional[int] = None
    created_at: Optional[str] = None


@dataclass
class HistoryItem:
    title: str
    url: str
    platform: str = "geral"
    action_type: str = "download"
    id: Optional[int] = None
    created_at: Optional[str] = None