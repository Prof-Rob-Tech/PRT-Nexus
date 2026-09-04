import yt_dlp

class TikTokConnector:
    def __init__(self):
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            # User-agent para evitar bloqueios de scraping do TikTok
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
        }

    def get_info(self, url: str) -> dict:
        """Extrai metadados do vídeo do TikTok sem realizar o download."""
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    'status': 'success',
                    'id': info.get('id'),
                    'title': info.get('title', 'Vídeo do TikTok'),
                    'author': info.get('uploader') or info.get('creator', 'Desconhecido'),
                    'thumbnail': info.get('thumbnail'),
                    'duration': info.get('duration', 0),
                    'like_count': info.get('like_count', 0),
                    'comment_count': info.get('comment_count', 0),
                    'url': url
                }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }

    # No final do arquivo services/tiktok_connector.py:

if __name__ == "__main__":
    connector = TikTokConnector()
    video_data = connector.get_info("https://www.tiktok.com/@usuario/video/123456789")

    if video_data['status'] == 'success':
        print(f"Título: {video_data['title']}")
        print(f"Autor: {video_data['author']}")
    else:
        print(f"Erro ao obter dados: {video_data['message']}")