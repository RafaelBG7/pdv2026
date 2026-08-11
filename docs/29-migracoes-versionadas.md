# Migrações versionadas — banco central e tenants

## Objetivo e escopo

O Girofy usa Alembic por meio do Flask-Migrate para controlar alterações de schema. Existem duas árvores independentes: `migrations/central` para o banco configurado em `DATABASE_URL` e `migrations/tenant` para cada banco indicado por `database_path`. Cada banco mantém sua própria tabela `alembic_version`; qualquer falha interrompe o deploy antes da troca do container da aplicação.

Apesar de hoje ambos receberem toda a metadata dos modelos, as árvores são separadas para permitir a divisão futura de responsabilidades sem reescrever o histórico.

## Baseline e adoção sem perda de dados

As revisões `central_0001` e `tenant_0001` representam o schema completo em 10/08/2026. Em banco vazio, o baseline cria as tabelas. Em banco legado sem `alembic_version`, o serviço valida tabelas essenciais, aplica `stamp` no baseline e executa a reconciliação `0002`.

A reconciliação adiciona condicionalmente colunas históricas e índices, normaliza status de vendas e confirmação de e-mail e nunca apaga registros. Downgrades destrutivos estão bloqueados.

## Execução por ambiente

- testes: `test_create_all`, com SQLite isolado;
- desenvolvimento: `upgrade`, permitindo atualizar o banco local;
- produção: `verify`; o processo web apenas confirma que central e tenant estão no head e falha cedo se estiverem atrasados;
- `off`: reservado a ferramentas sem acesso ao schema.

Não há mais `create_all`, `ALTER TABLE` ou criação de índices no startup/requisição de produção. A sincronização de empresa/usuário para o tenant executa somente DML.

## Comandos operacionais

```bash
python scripts/schema_migrate.py central-current
python scripts/schema_migrate.py central-upgrade
python scripts/schema_migrate.py tenants-status
python scripts/schema_migrate.py tenants-upgrade
python scripts/schema_migrate.py upgrade-all
```

`upgrade-all` migra o central, lê as empresas e migra cada tenant sequencialmente. Para na primeira falha. `--continue-on-error` é somente para diagnóstico e não é usado no deploy.

## Deploy OCI e rollback

O workflow é serializado por `girofy-oci-deploy`. A publicação compila imagens, inicia MySQL/Redis, gera um `mysqldump --all-databases` obrigatório, executa `upgrade-all`, atualiza os serviços somente após sucesso e valida login e endpoints de dependências.

Se backup ou migration falhar, `set -e` encerra a publicação e a aplicação anterior continua ativa. Rollback de schema exige parar escritas, restaurar o dump pré-deploy e republicar a versão anterior; o Alembic não executa downgrade destrutivo automático.

## Separação Web e Windows

### Web/backend

O backend é proprietário dos schemas, migrations, backups, validações e revisões executadas na OCI.

### Aplicativo Windows

O Girofy Windows não executa Alembic nem acessa MySQL diretamente. Ele continua consumindo a API; esta infraestrutura não alterou contratos. Mudanças futuras de resposta da API exigirão compatibilidade do cliente em tarefa própria.

## Diagnóstico e segurança

- `sem revisão`: banco vazio ou legado ainda não adotado;
- `pendente`: revisão atual diferente do head;
- `inválido`: tabela ou coluna esperada ausente;
- dois heads: histórico divergente, bloqueado até existir merge revision;
- tenant com falha: o deploy para e não substitui a aplicação.

Os logs registram tipo, nome lógico do banco, revisão anterior, head, duração e erro, sem URL ou credenciais.
