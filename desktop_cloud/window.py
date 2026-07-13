from __future__ import annotations

import base64
import html
import inspect
import sys
import webbrowser
from pathlib import Path

from .config import DesktopConfig, storage_dir
from .connectivity import check_server_available
from .navigation import build_navigation_guard_script, is_navigation_allowed, should_open_externally


WINDOW_TITLE = "Girofy"
WINDOW_WIDTH = 1366
WINDOW_HEIGHT = 768
WINDOW_MIN_SIZE = (1024, 650)


def resource_path(relative_path: str) -> Path:
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base_path / relative_path


def _image_data_uri() -> str:
    logo_path = resource_path("desktop_cloud/resources/logo.png")
    if not logo_path.exists():
        logo_path = Path(__file__).resolve().parent.parent / "app/static/favicon-v2.png"
    if not logo_path.exists():
        return ""
    encoded = base64.b64encode(logo_path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def offline_html(message: str, status: str = "") -> str:
    logo = _image_data_uri()
    logo_markup = f'<img class="logo" src="{logo}" alt="Girofy">' if logo else '<div class="logo-text">G</div>'
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Girofy</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #07111e;
      --panel: #0f2133;
      --border: #1e7b8c;
      --text: #f6f8ff;
      --muted: #a8b6c8;
      --accent: #25d5e8;
      --accent-2: #8758ff;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{
      width: 100%;
      height: 100%;
      margin: 0;
      font-family: Inter, Segoe UI, Arial, sans-serif;
      background: radial-gradient(circle at top left, rgba(37, 213, 232, .18), transparent 30%),
        linear-gradient(135deg, #07111e 0%, #0b1427 55%, #151031 100%);
      color: var(--text);
    }}
    body {{
      display: grid;
      place-items: center;
      padding: 32px;
    }}
    .card {{
      width: min(620px, 100%);
      border: 1px solid rgba(37, 213, 232, .45);
      border-radius: 22px;
      background: rgba(15, 33, 51, .92);
      box-shadow: 0 28px 80px rgba(0, 0, 0, .35);
      padding: 42px;
      text-align: center;
    }}
    .logo {{
      width: 92px;
      height: 92px;
      border-radius: 24px;
      object-fit: cover;
      margin-bottom: 22px;
    }}
    .logo-text {{
      width: 92px;
      height: 92px;
      border-radius: 24px;
      margin: 0 auto 22px;
      display: grid;
      place-items: center;
      font-size: 54px;
      font-weight: 900;
      background: linear-gradient(135deg, var(--accent-2), var(--accent));
    }}
    h1 {{
      margin: 0 0 14px;
      font-size: clamp(30px, 4vw, 44px);
    }}
    p {{
      margin: 0 auto 26px;
      color: var(--muted);
      font-size: 18px;
      line-height: 1.45;
      max-width: 520px;
    }}
    .status {{
      min-height: 24px;
      margin-bottom: 24px;
      color: #ffd166;
      font-weight: 800;
    }}
    .actions {{
      display: flex;
      gap: 14px;
      justify-content: center;
      flex-wrap: wrap;
    }}
    button {{
      border: 1px solid rgba(255,255,255,.16);
      border-radius: 14px;
      padding: 14px 22px;
      color: var(--text);
      background: #13243a;
      font-size: 17px;
      font-weight: 800;
      cursor: pointer;
    }}
    .primary {{
      border: 0;
      background: linear-gradient(135deg, var(--accent-2), var(--accent));
    }}
  </style>
</head>
<body>
  <main class="card">
    {logo_markup}
    <h1>Não foi possível conectar ao Girofy</h1>
    <p>{html.escape(message)}</p>
    <div id="status" class="status">{html.escape(status)}</div>
    <div class="actions">
      <button class="primary" onclick="retry()">Tentar novamente</button>
      <button onclick="closeApp()">Fechar</button>
    </div>
  </main>
  <script>
    function setStatus(text) {{
      document.getElementById('status').textContent = text || '';
    }}
    function retry() {{
      setStatus('Testando conexão...');
      window.pywebview.api.retry().then(function (result) {{
        if (!result.ok) setStatus(result.message || 'Servidor indisponível.');
      }});
    }}
    function closeApp() {{
      window.pywebview.api.close();
    }}
  </script>
</body>
</html>"""


class LauncherApi:
    def __init__(self, config: DesktopConfig, logger) -> None:
        self.config = config
        self.logger = logger
        self.window = None

    def retry(self) -> dict[str, object]:
        result = check_server_available(self.config)
        self.logger.info("retry_connectivity ok=%s status=%s", result.ok, result.status_code)
        if result.ok and self.window:
            self.window.load_url(self.config.app_url)
        return {"ok": result.ok, "message": result.message}

    def close(self) -> None:
        if self.window:
            self.window.destroy()

    def open_external(self, url: str) -> None:
        if should_open_externally(url, self.config):
            self.logger.info("open_external_url")
            webbrowser.open(url)

    def is_navigation_allowed(self, url: str) -> bool:
        return is_navigation_allowed(url, self.config)


def _configure_webview(webview_module, config: DesktopConfig) -> None:
    settings = getattr(webview_module, "settings", None)
    if isinstance(settings, dict):
        settings["ALLOW_DOWNLOADS"] = True
        settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False
        settings["USER_AGENT"] = config.user_agent


def open_window(config: DesktopConfig, logger, offline_message: str | None = None) -> None:
    import webview

    _configure_webview(webview, config)
    storage_dir().mkdir(parents=True, exist_ok=True)

    api = LauncherApi(config, logger)
    initial_url = config.app_url if offline_message is None else offline_html(offline_message)
    create_window_kwargs = {
        "js_api": api,
        "width": WINDOW_WIDTH,
        "height": WINDOW_HEIGHT,
        "min_size": WINDOW_MIN_SIZE,
        "resizable": True,
        "text_select": True,
    }
    supported_create_args = inspect.signature(webview.create_window).parameters
    create_window_kwargs = {
        key: value for key, value in create_window_kwargs.items() if key in supported_create_args
    }
    window = webview.create_window(WINDOW_TITLE, initial_url, **create_window_kwargs)
    api.window = window

    def inject_navigation_guard() -> None:
        try:
            window.evaluate_js(build_navigation_guard_script(config))
        except Exception as exc:
            logger.warning("navigation_guard_injection_failed %s", exc.__class__.__name__)

    try:
        window.events.loaded += inject_navigation_guard
    except Exception:
        logger.warning("navigation_guard_event_unavailable")

    start_kwargs = {
        "debug": False,
        "storage_path": str(storage_dir()),
        "user_agent": config.user_agent,
    }
    supported_start_args = inspect.signature(webview.start).parameters
    start_kwargs = {key: value for key, value in start_kwargs.items() if key in supported_start_args}
    webview.start(**start_kwargs)
