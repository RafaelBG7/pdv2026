# 16 - Manutenção

## Guia para Novos Desenvolvedores

1. Leia `README.md`.
2. Leia `docs/01-visao-geral.md`.
3. Leia `docs/03-arquitetura.md`.
4. Leia `docs/04-modelagem-banco.md`.
5. Leia os modelos em `app/models/`.
6. Leia as rotas em `app/routes/`.
7. Execute os testes.
8. Faça uma venda manual em ambiente local.

## Rodar Localmente

```bash
cd /Users/rafaelborges/pdv-adega-jf
source .venv/bin/activate
python app.py
```

Acesse:

```text
http://127.0.0.1:5001
```

## Criar Nova Funcionalidade

1. Definir regra de negócio.
2. Identificar domínio: `auth`, `catalog`, `main` ou novo módulo.
3. Verificar se a informação é central ou pertence à adega.
4. Criar/alterar modelo.
5. Ajustar criação/compatibilidade de colunas se necessário.
6. Criar rota.
7. Criar template.
8. Aplicar permissão no backend.
9. Adicionar teste.
10. Atualizar documentação.

## Banco Central ou Banco da Adega

Use banco central para:

- Empresas.
- Usuários.
- Keys.
- Assinatura.
- Dados do painel master.

Use banco da adega para:

- Produtos.
- Categorias.
- Vendas.
- Caixa.
- Pagamentos.
- Contas a pagar.

## Criar Nova Rota

1. Usar `@login_required` quando não for pública.
2. Usar `@permission_required` se a ação for sensível.
3. Usar `tenant_session()` para dados operacionais da adega.
4. Validar entradas do formulário.
5. Usar `flash()` para mensagens.
6. Usar redirect após POST bem-sucedido.
7. Criar teste de acesso permitido e negado.

## Criar Nova Tabela

Estado atual:

- Criar model em `app/models/`.
- Exportar em `app/models/__init__.py`.
- Garantir criação no banco correto.
- Se for operacional, garantir criação em bancos de tenant.

Recomendação profissional:

- Adicionar Flask-Migrate/Alembic.
- Criar migração versionada.
- Testar upgrade e downgrade.

## Backup

O backup atual é gerado por adega em arquivo `.sql` dentro de:

```text
backups/
```

Pode ser:

- Manual.
- Diário.
- Semanal.
- Mensal.

Configuração:

- Configurações > Backup.

Recomendação:

- Copiar os arquivos para armazenamento externo.
- Testar restauração periodicamente.
- Não considerar backup válido até testar restauração.

## Logs

Logs de erro ficam em:

```text
logs/errors.log
```

O master do sistema também vê logs recentes no painel master e pode limpar o arquivo.

## Corrigir Bug

1. Reproduzir.
2. Criar ou ajustar teste.
3. Corrigir a menor área possível.
4. Rodar testes.
5. Validar manualmente se for fluxo visual.
6. Atualizar documentação se a regra mudou.

## Antes de Produção

- Remover `debug=True`.
- Definir `SECRET_KEY` segura.
- Ativar CSRF.
- Criar usuário MySQL dedicado.
- Configurar HTTPS.
- Configurar backup externo.
- Adicionar migrações versionadas.
- Criar auditoria de ações críticas.
