from __future__ import annotations

import json
from urllib.parse import urljoin, urlparse

from .config import DesktopConfig, is_host_allowed


EXTERNAL_SCHEMES = {"mailto", "tel", "sms", "whatsapp"}


def is_navigation_allowed(url: str, config: DesktopConfig, current_url: str | None = None) -> bool:
    absolute_url = urljoin(current_url or config.app_url, url)
    parsed = urlparse(absolute_url)
    if parsed.scheme in EXTERNAL_SCHEMES:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.scheme == "http" and (config.is_production or not config.allow_http):
        return False
    return is_host_allowed(parsed.hostname, config.allowed_hosts)


def should_open_externally(url: str, config: DesktopConfig, current_url: str | None = None) -> bool:
    absolute_url = urljoin(current_url or config.app_url, url)
    parsed = urlparse(absolute_url)
    if parsed.scheme in EXTERNAL_SCHEMES:
        return True
    if parsed.scheme in {"http", "https"}:
        return not is_navigation_allowed(absolute_url, config)
    return False


def build_navigation_guard_script(config: DesktopConfig) -> str:
    exact_hosts = [host for host in config.allowed_hosts if not host.startswith(".")]
    suffix_hosts = [host for host in config.allowed_hosts if host.startswith(".")]
    payload = {
        "exactHosts": exact_hosts,
        "suffixHosts": suffix_hosts,
        "allowHttp": config.allow_http and not config.is_production,
    }
    return f"""
(function () {{
  const girofyDesktop = {json.dumps(payload)};
  function allowed(url) {{
    try {{
      const parsed = new URL(url, window.location.href);
      if (!['http:', 'https:'].includes(parsed.protocol)) return false;
      if (parsed.protocol === 'http:' && !girofyDesktop.allowHttp) return false;
      const host = parsed.hostname.toLowerCase();
      if (girofyDesktop.exactHosts.includes(host)) return true;
      return girofyDesktop.suffixHosts.some((suffix) => host.endsWith(suffix.toLowerCase()));
    }} catch (error) {{
      return false;
    }}
  }}
  document.addEventListener('click', function (event) {{
    const anchor = event.target.closest && event.target.closest('a[href]');
    if (!anchor) return;
    const href = anchor.getAttribute('href');
    if (!href || href.startsWith('#')) return;
    const absolute = new URL(href, window.location.href).href;
    if (anchor.target === '_blank' || !allowed(absolute)) {{
      event.preventDefault();
      if (window.pywebview && window.pywebview.api) {{
        window.pywebview.api.open_external(absolute);
      }}
    }}
  }}, true);
}})();
"""
