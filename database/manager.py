"""
===========================================================
PRT Nexus - Database Manager
Class: DatabaseManager
Description: Gerenciador central SQLite local (nexus.db).
===========================================================
"""

import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from database.models import DownloadItem

logger = logging.getLogger("PRTNexus.Database")


class DatabaseManager:
    """Gerenciador central do SQLite com suporte a thread-safety e modo WAL."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True

        if db_path:
            self.db_path = Path(db_path)
        else:
            base_dir = Path(__file__).resolve().parent
            self.db_path = base_dir / "nexus.db"

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Cria uma conexão isolada e segura por chamada/thread."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # Otimizações de concorrência para PySide6
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_db(self) -> None:
        """Cria as tabelas caso não existam."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS downloads (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        task_id TEXT UNIQUE,
                        title TEXT NOT NULL,
                        url TEXT NOT NULL,
                        platform TEXT,
                        file_path TEXT,
                        file_size TEXT,
                        status TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS favorites (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        url TEXT NOT NULL,
                        platform TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        url TEXT NOT NULL,
                        platform TEXT,
                        action_type TEXT DEFAULT 'download',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                conn.commit()
                logger.info(f"Banco de dados inicializado em: {self.db_path}")
        except Exception as e:
            logger.error(f"Erro ao inicializar banco de dados: {e}", exc_info=True)

    # ==========================================
    # DOWNLOADS / BIBLIOTECA
    # ==========================================

    def add_download(self, item: DownloadItem) -> int:
        """Registra ou atualiza um download na biblioteca."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO downloads (task_id, title, url, platform, file_path, file_size, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (item.task_id, item.title, item.url, item.platform, item.file_path, item.file_size, item.status))
            conn.commit()
            return cursor.lastrowid or 0

    def get_all_downloads(self) -> List[Dict[str, Any]]:
        """Retorna todos os downloads cadastrados."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM downloads ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    # ==========================================
    # FAVORITOS
    # ==========================================

    def add_favorite(self, title: str, url: str, platform: str = "geral") -> int:
        """Adiciona um item aos favoritos."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO favorites (title, url, platform)
                VALUES (?, ?, ?)
            """, (title, url, platform))
            conn.commit()
            return cursor.lastrowid or 0

    def get_all_favorites(self) -> List[Dict[str, Any]]:
        """Retorna todos os favoritos."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM favorites ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    def remove_favorite(self, fav_id: int) -> None:
        """Remove um item dos favoritos pelo ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM favorites WHERE id = ?", (fav_id,))
            conn.commit()

    def delete_favorite(self, fav_id: int) -> None:
        """Alias de remove_favorite para chamadas da interface."""
        self.remove_favorite(fav_id)

    # ==========================================
    # HISTÓRICO
    # ==========================================

    def add_history(self, title: str, url: str, platform: str = "geral", action_type: str = "download") -> int:
        """Adiciona uma entrada ao histórico."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO history (title, url, platform, action_type)
                VALUES (?, ?, ?, ?)
            """, (title, url, platform, action_type))
            conn.commit()
            return cursor.lastrowid or 0

    def get_all_history(self) -> List[Dict[str, Any]]:
        """Retorna todo o histórico de atividades."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM history ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    def clear_history(self) -> None:
        """Limpa todo o histórico de atividades."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM history")
            conn.commit()


# Instância global Singleton
db_manager = DatabaseManager()