"""Loopback-only static React build server. No public deployment or external bind."""
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
from functools import partial
import os
root=Path(__file__).resolve().parents[1]/'dist'
class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control','no-store');super().end_headers()
if __name__=='__main__':
    print('Silicon Watch local dashboard: http://127.0.0.1:5173',flush=True)
    ThreadingHTTPServer(('127.0.0.1',int(os.getenv('FRONTEND_PORT','5173'))),partial(Handler,directory=str(root))).serve_forever()
