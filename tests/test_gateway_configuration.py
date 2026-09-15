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

    def test_marketing_homepage_is_proxied_instead_of_redirected_to_login(self):
        block = self.server_block('www.skygest.com.br')
        root_location = block.split('location = / {', 1)[1].split('}', 1)[0]

        self.assertIn('proxy_pass http://127.0.0.1:5003;', root_location)
        self.assertNotIn('/login', root_location)

    def test_application_has_its_own_domain_and_login_entrypoint(self):
        block = self.server_block('app.skygest.com.br')

        self.assertIn('location = / {', block)
        self.assertIn('return 302 /login;', block)
        self.assertIn('proxy_pass http://127.0.0.1:5003;', block)

    def test_apex_redirects_to_canonical_marketing_homepage(self):
        block = self.server_block('skygest.com.br')

        self.assertIn('return 301 https://www.skygest.com.br$request_uri;', block)


if __name__ == '__main__':
    unittest.main()
