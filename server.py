from http.server import HTTPServer, SimpleHTTPRequestHandler
import os

class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # Разрешаем загрузку файлов
        self.send_header('Access-Control-Allow-Origin', '*')
        SimpleHTTPRequestHandler.end_headers(self)
    
    # Подавляем лишние логи
    def log_message(self, format, *args):
        pass

def run():
    port = int(os.environ.get('PORT', 10000))
    server_address = ('', port)
    httpd = HTTPServer(server_address, Handler)
    print(f"🚀 Сайт запущен на порту {port}")
    print(f"🌐 Откройте: https://telegram-shop-bot.onrender.com")
    httpd.serve_forever()

if __name__ == '__main__':
    run()
