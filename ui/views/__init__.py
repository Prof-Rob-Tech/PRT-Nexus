"""
===========================================================
PRT Nexus - Views Package
===========================================================
"""

from ui.views.browser_view import BrowserView
from ui.views.chip7_view import Chip7View
from ui.views.downloads_view import DownloadsView
from ui.views.favorites_view import FavoritesView
from ui.views.history_view import HistoryView
from ui.views.home_view import HomeView
from ui.views.kiwify_view import KiwifyView
from ui.views.library_view import LibraryView
from ui.views.tiktok_view import TikTokView
from ui.views.youtube_view import YouTubeView

__all__ = [
    "BrowserView",
    "Chip7View",
    "DownloadsView",
    "FavoritesView",
    "HistoryView",
    "HomeView",
    "KiwifyView",
    "LibraryView",
    "TikTokView",
    "YouTubeView",
]