# 16 - Manutenção

## Guia para Novos Desenvolvedores

1. Leia `README.md`.
2. Leia `docs/03-arquitetura.md`.
3. Leia modelos em `app/models/`.
4. Leia rotas em `app/routes/`.
5. Execute os testes.
6. Faça uma venda manual em ambiente local.

## Criar Nova Funcionalidade

Procedimento:

1. Definir regra de negócio.
2. Identificar domínio: auth, catalog, main ou novo blueprint.
3. Criar ou alterar modelo, se necessário.
4. Criar migração formal ou, no estado atual, função de compatibilidade temporária.
5. Criar rota.
6. Criar template.
7. Adicionar validações no servidor.
8. Adicionar testes.
9. Atualizar documentação.

## Criar Nova Tela

1. Criar template em `app/templates/`.
2. Estender `base.html`.
3. Criar rota no blueprint adequado.
4. Adicionar link no menu, se aplicável.
5. Adicionar CSS se necessário.
6. Adicionar JavaScript usando atributos `data-*`, seguindo padrão atual.
7. Adicionar teste de carregamento e permissão.

## Criar Nova Rota

1. Escolher blueprint.
2. Usar `@login_required` quando não for pública.
3. Validar entradas do formulário.
4. Usar `flash()` para mensagens ao usuário.
5. Usar `redirect(url_for(...))` após POST bem-sucedido.
6. Tratar `IntegrityError` quando houver unicidade.

## Criar Nova Tabela

Estado atual:

- Criar model em `app/models/`.
- Exportar em `app/models/__init__.py`.
- `db.create_all()` criará a tabela em bancos novos.

Recomendação profissional:

- Adicionar Flask-Migrate/Alembic.
- Criar migração versionada.
- Testar upgrade e downgrade.

## Criar Relatório

1. Definir período e filtros.
2. Criar função auxiliar em `main.py` ou serviço específico.
3. Buscar dados com SQLAlchemy.
4. Agregar valores no backend.
5. Renderizar cards/tabelas/gráficos.
6. Testar com dados conhecidos.

## Criar Permissão

1. Definir perfil no modelo de usuário.
2. Criar decorator de autorização.
3. Aplicar em rotas sensíveis.
4. Ajustar menu para esconder ações indisponíveis.
5. Garantir bloqueio no servidor, não apenas no frontend.
6. Criar testes por perfil.

## Corrigir Bug

1. Reproduzir.
2. Criar teste que falha.
3. Corrigir com menor alteração segura.
4. Executar testes.
5. Atualizar documentação se mudar comportamento.

## Atualizar Dependências

1. Revisar `requirements.txt`.
2. Atualizar em ambiente isolado.
3. Executar testes.
4. Validar login, catálogo, venda e relatório.
5. Registrar mudanças relevantes.

## Backup

Backup manual do SQLite:

```bash
cp database/adega_jf.db backups/adega_jf-$(date +%Y%m%d-%H%M%S).db
```

Recomendações:

- Parar aplicação ou usar API de backup SQLite para consistência.
- Guardar cópia fora da máquina.
- Testar restauração periodicamente.

## Restauração

1. Parar aplicação.
2. Fazer cópia do banco atual.
3. Substituir `database/adega_jf.db` pelo backup.
4. Iniciar aplicação.
5. Validar dados.

## Rollback de Código

1. Identificar versão anterior estável.
2. Parar aplicação.
3. Retornar código.
4. Restaurar banco, se schema mudou.
5. Rodar testes.
6. Subir aplicação.

## Pontos de Atenção

- Não excluir o banco local sem backup.
- Não usar senha padrão em produção.
- Não confiar em validação apenas do JavaScript.
- Não editar schema manualmente sem registrar.
- Não habilitar múltiplos processos de escrita pesada em SQLite sem análise.
