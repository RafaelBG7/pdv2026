import os
import socket
import subprocess
import sys
import time
import traceback
import webbrowser
from pathlib import Path

from werkzeug.serving import make_server


APP_NAME = 'Girofy PDV'
DEFAULT_PORT = 5003


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
        from app import create_app

        app = create_app()
        server = make_server('127.0.0.1', port, app)
    except Exception:
        log_path = base_dir / 'launcher-error.log'
        log_path.write_text(traceback.format_exc(), encoding='utf-8')
        show_error('Não foi possível iniciar o Girofy PDV.', log_path)
        return 1

    url = f'http://127.0.0.1:{port}/'
    webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
    except Exception:
        log_path = base_dir / 'launcher-error.log'
        log_path.write_text(traceback.format_exc(), encoding='utf-8')
        show_error('O Girofy PDV foi encerrado por uma falha inesperada.', log_path)
        return 1

    time.sleep(0.2)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
