from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from . import APP_VERSION
from .config import DesktopConfig, is_host_allowed, updates_dir


@dataclass(frozen=True)
class UpdateInfo:
    available: bool
    current_version: str = APP_VERSION
    version: str = ""
    installer_url: str = ""
    release_url: str = ""
    notes: str = ""
    sha256: str = ""
    message: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "available": self.available,
            "current_version": self.current_version,
            "version": self.version,
            "installer_url": self.installer_url,
            "release_url": self.release_url,
            "notes": self.notes,
            "sha256": self.sha256,
            "message": self.message,
        }


def _version_parts(version: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", (version or "").lstrip("vV"))
    return tuple(int(number) for number in numbers[:4]) or (0,)


def is_newer_version(remote_version: str, current_version: str = APP_VERSION) -> bool:
    remote = _version_parts(remote_version)
    current = _version_parts(current_version)
    size = max(len(remote), len(current))
    return remote + (0,) * (size - len(remote)) > current + (0,) * (size - len(current))


def _request_json(url: str, config: DesktopConfig) -> dict[str, object]:
    request = Request(url, headers={"User-Agent": config.user_agent, "Accept": "application/json"})
    with urlopen(request, timeout=config.timeout_seconds) as response:
        payload = response.read(1024 * 1024)
    decoded = json.loads(payload.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("Manifesto de atualização inválido.")
    return decoded


def _is_url_allowed(url: str, config: DesktopConfig) -> bool:
    parsed = urlparse(url or "")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    if parsed.scheme == "http" and (config.is_production or not config.allow_http):
        return False
    return is_host_allowed(parsed.hostname, config.allowed_hosts)


def check_for_update(config: DesktopConfig) -> UpdateInfo:
    if not config.auto_update_enabled:
        return UpdateInfo(False, message="Atualização automática desativada.")
    if not config.update_manifest_url:
        return UpdateInfo(False, message="Manifesto de atualização não configurado.")
    if not _is_url_allowed(config.update_manifest_url, config):
        return UpdateInfo(False, message="Servidor de atualização bloqueado.")

    manifest = _request_json(config.update_manifest_url, config)
    version = str(manifest.get("version") or "").strip()
    installer_url = str(manifest.get("installer_url") or "").strip()
    release_url = str(manifest.get("release_url") or "").strip()
    notes = str(manifest.get("notes") or "").strip()
    sha256 = str(manifest.get("sha256") or "").strip().lower()

    if not version or not installer_url:
        return UpdateInfo(False, message="Nenhuma atualização publicada.")
    if not _is_url_allowed(installer_url, config):
        return UpdateInfo(False, message="Instalador bloqueado pela allowlist.")
    if release_url and not _is_url_allowed(release_url, config):
        release_url = ""

    return UpdateInfo(
        available=is_newer_version(version),
        version=version,
        installer_url=installer_url,
        release_url=release_url,
        notes=notes,
        sha256=sha256,
    )


def _download_path(version: str) -> Path:
    safe_version = re.sub(r"[^A-Za-z0-9._-]+", "-", version or "latest").strip("-") or "latest"
    return updates_dir() / f"Girofy-Setup-{safe_version}.exe"


def download_update(update: UpdateInfo, config: DesktopConfig) -> Path:
    if not update.available or not update.installer_url:
        raise ValueError("Nenhuma atualização disponível para download.")
    if not _is_url_allowed(update.installer_url, config):
        raise ValueError("Instalador bloqueado pela configuração de segurança.")

    destination = _download_path(update.version)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = destination.with_suffix(".download")
    request = Request(update.installer_url, headers={"User-Agent": config.user_agent})
    digest = hashlib.sha256()

    with urlopen(request, timeout=max(config.timeout_seconds, 10.0)) as response:
        with temporary_path.open("wb") as output:
            while True:
                chunk = response.read(1024 * 256)
                if not chunk:
                    break
                digest.update(chunk)
                output.write(chunk)

    if update.sha256 and digest.hexdigest().lower() != update.sha256.lower():
        temporary_path.unlink(missing_ok=True)
        raise ValueError("Assinatura SHA-256 do instalador não confere.")

    os.replace(temporary_path, destination)
    return destination


def launch_installer(installer_path: Path, *, silent: bool = False) -> None:
    if not installer_path.exists():
        raise FileNotFoundError(str(installer_path))
    command = [str(installer_path)]
    if silent:
        command.extend(["/SILENT", "/NORESTART", "/SP-"])
    subprocess.Popen(command, close_fds=True)
