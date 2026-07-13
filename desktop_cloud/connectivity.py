from __future__ import annotations

import socket
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlparse

from .config import DesktopConfig


@dataclass(frozen=True)
class ConnectivityResult:
    ok: bool
    message: str
    status_code: int | None = None


def can_reach_host(url: str, timeout: float = 3.0) -> bool:
    parsed = urlparse(url)
    if not parsed.hostname:
        return False
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((parsed.hostname, port), timeout=timeout):
            return True
    except OSError:
        return False


def check_server_available(config: DesktopConfig) -> ConnectivityResult:
    if not can_reach_host(config.app_url, min(config.timeout_seconds, 2.0)):
        return ConnectivityResult(False, "Sem conexão com o servidor do Girofy.")

    request = urllib.request.Request(
        config.app_url,
        headers={
            "User-Agent": config.user_agent,
            "Cache-Control": "no-cache",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=config.timeout_seconds,
            context=ssl.create_default_context(),
        ) as response:
            if response.status < 500:
                return ConnectivityResult(True, "Servidor disponível.", response.status)
            return ConnectivityResult(False, "O servidor do Girofy respondeu com erro.", response.status)
    except urllib.error.HTTPError as exc:
        if exc.code < 500:
            return ConnectivityResult(True, "Servidor disponível.", exc.code)
        return ConnectivityResult(False, "O servidor do Girofy respondeu com erro.", exc.code)
    except urllib.error.URLError as exc:
        return ConnectivityResult(False, f"Não foi possível conectar ao Girofy: {exc.reason}")
    except TimeoutError:
        return ConnectivityResult(False, "A conexão com o Girofy expirou.")
    except Exception as exc:
        return ConnectivityResult(False, f"Falha ao testar conexão com o Girofy: {exc.__class__.__name__}")
