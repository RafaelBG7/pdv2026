import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProductionGatewayConfigurationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = (ROOT / 'deploy/nginx/skygest-production.conf').read_text()

    def server_block(self, domain):
        for block in self.config.split('server {')[1:]:
            if f'server_name {domain};' in block:
                return block
        self.fail(f'Bloco Nginx não encontrado para {domain}')

    def test_apex_serves_homepage_login_and_application(self):
        block = self.server_block('skygest.com.br')
        self.assertIn('location / {', block)
        self.assertIn('proxy_pass http://127.0.0.1:5003;', block)
        self.assertNotIn('return 302', block)

    def test_http_redirects_to_apex_preserving_path(self):
        block = next(block for block in self.config.split('server {')[1:] if 'listen 80;' in block)
        self.assertIn('return 301 https://skygest.com.br$request_uri;', block)

    def test_legacy_hosts_use_method_preserving_redirect(self):
        block = next(
            block for block in self.config.split('server {')[1:]
            if 'server_name www.skygest.com.br app.skygest.com.br;' in block
        )
        self.assertIn('return 308 https://skygest.com.br$request_uri;', block)


if __name__ == '__main__':
    unittest.main()
