# Workflows, deploy e artefatos

## Componentes independentes

| Workflow | Arquivo | Efeito |
|---|---|---|
| Windows WPF | `.github/workflows/build-windows-wpf.yml` | Testa/publica o cliente, gera o instalador Inno Setup e atualiza a release de prévia. |
| OCI self-hosted | `.github/workflows/deploy-oci-self-hosted.yml` | Testa migrations/backend e implanta Web/API no runner da OCI. |
| OCI remoto | `.github/workflows/deploy-oci.yml` | Alternativa de deploy remoto conforme secrets configurados. |

Uma alteração somente visual do WPF não exige migration nem deploy Web. Uma alteração em API/serviço exige deploy Web/API e depois validação do App compatível. Mudanças de schema devem passar pelas trilhas Alembic central e tenant antes da aplicação iniciar.

## Artefatos Windows

O build 0.8.0 gera o executável self-contained `Girofy.exe` e o instalador de desenvolvimento `GiroFy-Setup-0.8.0.exe`. Os artifacts temporários têm retenção de sete dias; a release pre-release `windows-preview` mantém os dois arquivos atuais. Falha `Artifact storage quota has been hit` é cota da conta, não falha de compilação. Após excluir artifacts antigos, o GitHub pode levar 6–12 horas para recalcular o uso.

O instalador usa Inno Setup, instala por usuário em `%LocalAppData%\Programs\GiroFy`, cria atalho no Menu Iniciar e preserva `%LocalAppData%\Girofy` na desinstalação. Consulte [WINDOWS_INSTALLER.md](WINDOWS_INSTALLER.md).

## Ordem segura de publicação

1. Executar testes Python e WPF.
2. Aplicar migrations compatíveis com a versão anterior.
3. Publicar Web/API e validar `/health` e `/health/dependencies`.
4. Publicar o Windows e validar login, venda idempotente, caixa e estoque.
5. Observar logs e manter rollback do componente afetado.

Nunca incorporar credenciais, banco ou segredos no executável. O App deve continuar consumindo a API versionada.
