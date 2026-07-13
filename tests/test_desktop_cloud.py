import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from desktop_cloud.config import ConfigError, DesktopConfig, is_host_allowed, load_desktop_config, validate_desktop_config
from desktop_cloud.navigation import is_navigation_allowed, should_open_externally


class DesktopCloudConfigTestCase(unittest.TestCase):
    def test_production_accepts_official_https_url(self):
        config = validate_desktop_config(DesktopConfig(app_url="https://app.girofy.com.br/login"))

        self.assertEqual(config.app_url, "https://app.girofy.com.br/login")

    def test_production_rejects_http_url(self):
        with self.assertRaises(ConfigError):
            validate_desktop_config(DesktopConfig(app_url="http://app.girofy.com.br"))

    def test_development_allows_http_when_explicitly_enabled(self):
        config = DesktopConfig(
            app_url="http://168.75.101.126:18080",
            allowed_hosts=("168.75.101.126",),
            allow_http=True,
            environment="development",
        )

        self.assertEqual(validate_desktop_config(config).app_url, "http://168.75.101.126:18080/")

    def test_rejects_unsafe_schemes_and_credentials(self):
        for url in ["file:///tmp/index.html", "javascript:alert(1)", "https://user:pass@app.girofy.com.br"]:
            with self.subTest(url=url):
                with self.assertRaises(ConfigError):
                    validate_desktop_config(DesktopConfig(app_url=url))

    def test_rejects_unknown_host(self):
        with self.assertRaises(ConfigError):
            validate_desktop_config(DesktopConfig(app_url="https://evil.example.com"))

    def test_host_allowlist_supports_exact_and_suffix_hosts(self):
        self.assertTrue(is_host_allowed("app.girofy.com.br", ("app.girofy.com.br",)))
        self.assertTrue(is_host_allowed("loja.girofy.com.br", (".girofy.com.br",)))
        self.assertFalse(is_host_allowed("girofy.com.br.evil.test", (".girofy.com.br",)))

    def test_loads_config_file_and_environment_overrides(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "desktop.json"
            config_file.write_text(
                json.dumps(
                    {
                        "app_url": "https://app.girofy.com.br",
                        "allowed_hosts": ["app.girofy.com.br"],
                    }
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"GIROFY_DESKTOP_APP_URL": "https://loja.girofy.com.br"}, clear=False):
                config = load_desktop_config(config_file)

        self.assertEqual(config.app_url, "https://loja.girofy.com.br")


class DesktopCloudNavigationTestCase(unittest.TestCase):
    def test_allows_internal_navigation(self):
        config = DesktopConfig(app_url="https://app.girofy.com.br")

        self.assertTrue(is_navigation_allowed("/vendas", config))

    def test_blocks_unknown_domain_inside_window(self):
        config = DesktopConfig(app_url="https://app.girofy.com.br")

        self.assertFalse(is_navigation_allowed("https://example.com", config))
        self.assertTrue(should_open_externally("https://example.com", config))

    def test_opens_mail_and_whatsapp_externally(self):
        config = DesktopConfig(app_url="https://app.girofy.com.br")

        self.assertTrue(should_open_externally("mailto:suporte@girofy.com.br", config))
        self.assertTrue(should_open_externally("whatsapp://send?phone=5500000000000", config))


if __name__ == "__main__":
    unittest.main()
