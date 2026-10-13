"""Require the exact tree successfully deployed by the HML workflow."""
import json
import os
import re
import subprocess
from urllib.request import Request, urlopen


def verify():
    sha = os.environ.get('VALIDATED_HML_SHA', '')
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise SystemExit('Informe o SHA completo validado manualmente em HML.')
    if os.environ.get('GITHUB_REF') != 'refs/heads/main':
        raise SystemExit('Produção aceita somente main.')
    tree = lambda ref: subprocess.check_output(['git', 'rev-parse', ref + '^{tree}']).strip()
    if tree(sha) != tree('HEAD'):
        raise SystemExit('O conteúdo difere do commit validado em HML.')
    repo = os.environ['GITHUB_REPOSITORY']
    request = Request(
        f'https://api.github.com/repos/{repo}/actions/workflows/deploy-hml-oci.yml/runs?head_sha={sha}&status=success',
        headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'], 'Accept': 'application/vnd.github+json'},
    )
    with urlopen(request, timeout=30) as response:
        runs = json.load(response)['workflow_runs']
    if not any(run['head_sha'] == sha and run['head_branch'] == 'develop'
               and run['event'] == 'push' and run['conclusion'] == 'success' for run in runs):
        raise SystemExit('Não há deploy HML bem-sucedido desse commit em develop.')
    print('Conteúdo idêntico ao deploy HML confirmado. Aprovação humana exigida pelo ambiente production.')


if __name__ == '__main__':
    verify()
