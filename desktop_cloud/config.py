from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from . import APP_VERSION


DEFAULT_APP_URL = "https://app.girofy.com.br"
DEFAULT_ALLOWED_HOSTS = ("app.girofy.com.br", ".girofy.com.br")
DEFAULT_USER_AGENT = f"GirofyDesktop/{APP_VERSION}"
DEFAULT_UPDATE_MANIFEST_PATH = "/desktop/update.json"


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class DesktopConfig:
    app_url: str = DEFAULT_APP_URL
    allowed_hosts: tuple[str, ...] = field(default_factory=lambda: DEFAULT_ALLOWED_HOSTS)
    allow_http: bool = False
    environment: str = "production"
    timeout_seconds: float = 2.0
    user_agent: str = DEFAULT_USER_AGENT
    auto_update_enabled: bool = True
    update_check_on_start: bool = True
    update_manifest_url: str = ""
    update_install_silent: bool = False

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


def parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "sim", "on"}


def program_data_dir() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Girofy"
    return Path(os.environ.get("GIROFY_DESKTOP_HOME", Path.home() / ".girofy"))


def config_path() -> Path:
    custom_path = os.environ.get("GIROFY_DESKTOP_CONFIG")
    if custom_path:
        return Path(custom_path).expanduser()
    return program_data_dir() / "config" / "desktop.json"


def bundled_config_path() -> Path:
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base_path / "desktop_cloud" / "resources" / "desktop.json"


def logs_dir() -> Path:
    return program_data_dir() / "logs"


def storage_dir() -> Path:
    return program_data_dir() / "webview"


def updates_dir() -> Path:
    return program_data_dir() / "updates"


def default_update_manifest_url(app_url: str) -> str:
    parsed = urlparse((app_url or DEFAULT_APP_URL).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return urlunparse((parsed.scheme, parsed.netloc.lower(), DEFAULT_UPDATE_MANIFEST_PATH, "", "", ""))


def _split_hosts(value: object) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        hosts = value
    else:
        hosts = str(value or "").split(",")
    return tuple(_normalize_host(host) for host in hosts if _normalize_host(host))


def _normalize_host(host: str | None) -> str:
    return (host or "").strip().lower().rstrip(".")


def is_host_allowed(host: str | None, allowed_hosts: tuple[str, ...]) -> bool:
    normalized = _normalize_host(host)
    if not normalized:
        return False
    for allowed in allowed_hosts:
        allowed = _normalize_host(allowed)
        if not allowed:
            continue
        if allowed.startswith(".") and normalized.endswith(allowed):
            return True
        if normalized == allowed:
            return True
    return False


def load_desktop_config(path: Path | None = None) -> DesktopConfig:
    data: dict[str, object] = {}
    chosen_path = path or config_path()
    if path is None and not chosen_path.exists() and bundled_config_path().exists():
        chosen_path = bundled_config_path()
    if chosen_path.exists():
        with chosen_path.open("r", encoding="utf-8") as config_file:
            loaded = json.load(config_file)
            if not isinstance(loaded, dict):
                raise ConfigError("O arquivo desktop.json precisa conter um objeto JSON.")
            data.update(loaded)

    if os.environ.get("GIROFY_DESKTOP_APP_URL"):
        data["app_url"] = os.environ["GIROFY_DESKTOP_APP_URL"]
    if os.environ.get("GIROFY_DESKTOP_ALLOWED_HOSTS"):
        data["allowed_hosts"] = os.environ["GIROFY_DESKTOP_ALLOWED_HOSTS"]
    if os.environ.get("GIROFY_DESKTOP_ALLOW_HTTP"):
        data["allow_http"] = os.environ["GIROFY_DESKTOP_ALLOW_HTTP"]
    if os.environ.get("GIROFY_DESKTOP_ENV"):
        data["environment"] = os.environ["GIROFY_DESKTOP_ENV"]
    if os.environ.get("GIROFY_DESKTOP_AUTO_UPDATE"):
        data["auto_update_enabled"] = os.environ["GIROFY_DESKTOP_AUTO_UPDATE"]
    if os.environ.get("GIROFY_DESKTOP_UPDATE_CHECK_ON_START"):
        data["update_check_on_start"] = os.environ["GIROFY_DESKTOP_UPDATE_CHECK_ON_START"]
    if os.environ.get("GIROFY_DESKTOP_UPDATE_MANIFEST_URL"):
        data["update_manifest_url"] = os.environ["GIROFY_DESKTOP_UPDATE_MANIFEST_URL"]
    if os.environ.get("GIROFY_DESKTOP_UPDATE_INSTALL_SILENT"):
        data["update_install_silent"] = os.environ["GIROFY_DESKTOP_UPDATE_INSTALL_SILENT"]

    allowed_hosts = _split_hosts(data.get("allowed_hosts")) or DEFAULT_ALLOWED_HOSTS
    app_url = str(data.get("app_url") or DEFAULT_APP_URL).strip()
    return DesktopConfig(
        app_url=app_url,
        allowed_hosts=allowed_hosts,
        allow_http=parse_bool(data.get("allow_http")),
        environment=str(data.get("environment") or "production").strip().lower(),
        timeout_seconds=float(data.get("timeout_seconds") or 2),
        user_agent=str(data.get("user_agent") or DEFAULT_USER_AGENT).strip() or DEFAULT_USER_AGENT,
        auto_update_enabled=parse_bool(data.get("auto_update_enabled", True)),
        update_check_on_start=parse_bool(data.get("update_check_on_start", True)),
        update_manifest_url=str(
            data.get("update_manifest_url") or default_update_manifest_url(app_url)
        ).strip(),
        update_install_silent=parse_bool(data.get("update_install_silent")),
    )


def validate_desktop_config(config: DesktopConfig) -> DesktopConfig:
    parsed = urlparse(config.app_url.strip())
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise ConfigError("A URL do Girofy precisa usar HTTP ou HTTPS.")
    if parsed.username or parsed.password:
        raise ConfigError("A URL do Girofy não pode conter usuário ou senha.")
    if scheme == "http":
        if config.is_production:
            raise ConfigError("Em produção, o Girofy Desktop aceita apenas HTTPS.")
        if not config.allow_http:
            raise ConfigError("HTTP só pode ser usado quando allow_http estiver ativado.")
    if not parsed.netloc or not is_host_allowed(parsed.hostname, config.allowed_hosts):
        raise ConfigError("Domínio bloqueado pela configuração de segurança do Girofy Desktop.")

    normalized_update_url = ""
    if config.auto_update_enabled and config.update_manifest_url:
        update_parsed = urlparse(config.update_manifest_url.strip())
        update_scheme = update_parsed.scheme.lower()
        if update_scheme not in {"http", "https"}:
            raise ConfigError("A URL de atualização precisa usar HTTP ou HTTPS.")
        if update_parsed.username or update_parsed.password:
            raise ConfigError("A URL de atualização não pode conter usuário ou senha.")
        if update_scheme == "http":
            if config.is_production:
                raise ConfigError("Em produção, atualizações aceitam apenas HTTPS.")
            if not config.allow_http:
                raise ConfigError("Atualização por HTTP só pode ser usada quando allow_http estiver ativado.")
        if not update_parsed.netloc or not is_host_allowed(update_parsed.hostname, config.allowed_hosts):
            raise ConfigError("Servidor de atualização bloqueado pela allowlist do Girofy Desktop.")
        normalized_update_url = urlunparse(
            (
                update_scheme,
                update_parsed.netloc.lower(),
                update_parsed.path or DEFAULT_UPDATE_MANIFEST_PATH,
                "",
                update_parsed.query,
                "",
            )
        )

    normalized_path = parsed.path or "/"
    normalized_url = urlunparse(
        (
            scheme,
            parsed.netloc.lower(),
            normalized_path,
            "",
            "",
            "",
        )
    )
    return DesktopConfig(
        app_url=normalized_url,
        allowed_hosts=config.allowed_hosts,
        allow_http=config.allow_http,
        environment=config.environment,
        timeout_seconds=config.timeout_seconds,
        user_agent=config.user_agent,
        auto_update_enabled=config.auto_update_enabled,
        update_check_on_start=config.update_check_on_start,
        update_manifest_url=normalized_update_url,
        update_install_silent=config.update_install_silent,
    )
