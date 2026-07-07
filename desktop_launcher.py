import os
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
from pathlib import Path

from werkzeug.serving import make_server


APP_NAME = 'Girofy'
DEFAULT_PORT = 5003
WINDOW_WIDTH = 1366
WINDOW_HEIGHT = 820


def runtime_dir():
    if os.environ.get('APP_BASE_DIR'):
        return Path(os.environ['APP_BASE_DIR']).expanduser().resolve()

    if getattr(sys, 'frozen', False):
        executable_path = Path(sys.executable).resolve()
        candidates = [Path.cwd(), executable_path.parent, *executable_path.parents]
        for candidate in candidates:
            if (candidate / '.env').exists():
                return candidate
        return executable_path.parent

    return Path(__file__).resolve().parent


def find_free_port(preferred_port):
    for port in [preferred_port, *range(5010, 5060)]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(('127.0.0.1', port))
            except OSError:
                continue
            return port
    raise RuntimeError('Nenhuma porta local livre encontrada entre 5010 e 5059.')


def show_error(message, log_path):
    full_message = f'{message}\n\nDetalhes salvos em:\n{log_path}'
    if sys.platform == 'darwin':
        subprocess.run(
            [
                'osascript',
                '-e',
                f'display dialog "{full_message.replace(chr(34), chr(39))}" buttons {{"OK"}} with title "{APP_NAME}"',
            ],
            check=False,
        )
    else:
        print(full_message)


def wait_until_ready(url, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status < 500:
                    return True
        except Exception:
            time.sleep(0.25)
    return False


def main():
    base_dir = runtime_dir()
    os.environ.setdefault('APP_BASE_DIR', str(base_dir))
    os.environ.setdefault('APP_ENV', 'desktop')
    os.environ.setdefault('FLASK_DEBUG', 'false')

    preferred_port = int(os.environ.get('PORT', str(DEFAULT_PORT)))
    port = find_free_port(preferred_port)
    os.environ['PORT'] = str(port)
    os.environ.setdefault('PUBLIC_BASE_URL', f'http://127.0.0.1:{port}')

    try:
        import webview
        from app import create_app

        app = create_app()
        server = make_server('127.0.0.1', port, app)
    except Exception:
        log_path = base_dir / 'launcher-error.log'
        log_path.write_text(traceback.format_exc(), encoding='utf-8')
        show_error('Não foi possível iniciar o Girofy.', log_path)
        return 1

    url = f'http://127.0.0.1:{port}/'
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        if not wait_until_ready(url):
            raise RuntimeError(f'O servidor local não respondeu em {url}')

        if os.environ.get('APP_DESKTOP_SMOKE_TEST') == '1':
            print(url)
            return 0

        webview.create_window(
            APP_NAME,
            url,
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            min_size=(1024, 680),
        )
        webview.start(debug=False)
    except KeyboardInterrupt:
        pass
    except Exception:
        log_path = base_dir / 'launcher-error.log'
        log_path.write_text(traceback.format_exc(), encoding='utf-8')
        show_error('O Girofy foi encerrado por uma falha inesperada.', log_path)
        return 1
    finally:
        server.shutdown()

    time.sleep(0.2)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
