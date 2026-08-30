import os
from pathlib import Path
import subprocess
import sys
import unittest

from scripts.validate_environment_isolation import parse_env, validate_homologation


ROOT = Path(__file__).resolve().parents[1]


class EnvironmentIsolationTestCase(unittest.TestCase):
    def test_hml_example_uses_isolated_runtime_identifiers(self):
        values = parse_env(ROOT / '.env.hml.example')
        self.assertEqual(validate_homologation(values, validate_secrets=False), [])
        self.assertEqual(values['APP_ENV'], 'homologation')
        self.assertEqual(values['PUBLIC_BASE_URL'], 'https://hml.skygest.com.br')
        self.assertEqual(values['MYSQL_DATABASE'], 'skygest_hml_central')
        self.assertEqual(values['RATELIMIT_KEY_PREFIX'], 'skygest-hml')
        self.assertEqual(values['MAIL_SUPPRESS_SEND'], '1')

    def test_hml_rejects_secrets_shared_with_production(self):
        hml = parse_env(ROOT / '.env.hml.example')
        production = {field: hml.get(field) for field in (
            'SECRET_KEY',
            'API_TOKEN_SECRET',
            'MASTER_DEFAULT_PASSWORD',
            'MYSQL_PASSWORD',
            'MYSQL_ROOT_PASSWORD',
        )}
        errors = validate_homologation(hml, production, validate_secrets=False)
        self.assertTrue(any('compartilhado com produção' in error for error in errors))

    def test_hml_compose_has_dedicated_network_volumes_and_loopback_only(self):
        compose = (ROOT / 'docker-compose.hml.yml').read_text(encoding='utf-8')
        self.assertIn('name: skygest-hml', compose)
        self.assertIn('name: skygest_hml_internal', compose)
        self.assertIn('name: skygest_hml_mysql_data', compose)
        self.assertIn('127.0.0.1:${HML_LOOPBACK_PORT:-18081}:18081', compose)
        self.assertNotIn('3306:3306', compose)
        self.assertNotIn('6379:6379', compose)
        self.assertNotIn('/opt/girofy/backups', compose)

    def test_branch_workflows_cannot_cross_deploy_targets(self):
        production = (ROOT / '.github/workflows/deploy-oci-self-hosted.yml').read_text(encoding='utf-8')
        hml = (ROOT / '.github/workflows/deploy-hml-oci.yml').read_text(encoding='utf-8')
        self.assertIn('- main', production)
        self.assertNotIn('- develop', production)
        self.assertIn('- develop', hml)
        self.assertNotIn('deploy_self_hosted_app.sh', hml)
        self.assertIn('deploy_hml.sh', hml)

    def test_homologation_defaults_are_production_like(self):
        environment = os.environ.copy()
        environment.update({
            'APP_ENV': 'homologation',
            'SECRET_KEY': 'hml-secret-key-with-more-than-sixteen-characters',
            'API_TOKEN_SECRET': 'hml-api-token-with-more-than-sixteen-characters',
            'MASTER_DEFAULT_PASSWORD': 'HmlPassword123456',
            'RATELIMIT_STORAGE_URI': 'redis://redis:6379/0',
            'RATELIMIT_IN_MEMORY_FALLBACK_ENABLED': '0',
            'SCHEMA_MANAGEMENT_MODE': 'verify',
            'SESSION_COOKIE_SECURE': '1',
            'MAIL_SUPPRESS_SEND': '1',
        })
        result = subprocess.run(
            [
                sys.executable,
                '-c',
                'from config import Config; '
                "assert Config.SCHEMA_MANAGEMENT_MODE == 'verify'; "
                'assert Config.SESSION_COOKIE_SECURE is True; '
                'assert Config.MAIL_SUPPRESS_SEND is True; '
                'assert Config.RATELIMIT_IN_MEMORY_FALLBACK_ENABLED is False',
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
