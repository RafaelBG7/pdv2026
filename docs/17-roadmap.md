# 17 - Roadmap

## Versão Atual

Implementado:

- Flask monolítico.
- SQLite local.
- Login/logout/cadastro.
- Configurações do usuário.
- Catálogo de produtos e categorias.
- Produtos kit.
- Abertura e fechamento de caixa.
- Registro de venda.
- Múltiplas formas de pagamento.
- Desconto.
- Troco.
- Baixa automática de estoque.
- Relatórios por período.
- Alertas de estoque baixo.
- Testes automatizados principais.

Parcial:

- Dashboard.
- Segurança.
- Deploy.
- Permissões.
- Migrações.
- Monitoramento.

## Próxima Versão

Prioridade alta:

- Corrigir `app.py`.
- Remover `DEBUG=True` fixo.
- Exigir `SECRET_KEY` segura.
- Remover/proteger cadastro público.
- Forçar troca da senha padrão.
- Implementar CSRF.
- Implementar permissões por perfil.
- Criar migrações com Alembic/Flask-Migrate.
- Criar backup automatizado.
- Adicionar logs.

## Melhorias Futuras

Operação:

- Cancelamento de venda.
- Estorno.
- Sangria e reforço de caixa.
- Histórico de movimentação de estoque.
- Ajuste manual de estoque com motivo.
- Cadastro de fornecedores.
- Registro de compras.
- Cadastro de clientes.
- Impressão de comprovante.
- Exportação CSV/PDF.

Gestão:

- Dashboard com métricas reais.
- Curva ABC de produtos.
- Margem por categoria.
- Relatório de divergência de caixa.
- Relatório de estoque mínimo.

## Integrações Futuras

- Impressoras térmicas.
- Leitor de código de barras.
- TEF.
- Emissão fiscal, se aplicável.
- WhatsApp/email para relatórios.
- Sistema contábil.
- ERP.

## Escalabilidade

- PostgreSQL.
- API JSON.
- Separação frontend/backend.
- Paginação e busca indexada.
- Cache de relatórios.
- Processamento assíncrono.
- Deploy containerizado.

## Mobile

Possibilidades:

- PWA.
- Layout dedicado para operação em tablet.
- Scanner por câmera.
- App mobile para consulta de estoque.

## Desktop

Possibilidades:

- Empacotamento com Electron/Tauri.
- Instalador local.
- Sincronização controlada com servidor.

## API Pública

Planejada:

- `/api/v1/auth/login`.
- `/api/v1/products`.
- `/api/v1/categories`.
- `/api/v1/sales`.
- `/api/v1/cash-registers`.
- `/api/v1/reports`.

Requisitos:

- JWT ou sessão API.
- Rate limit.
- Versionamento.
- Documentação OpenAPI.
- Testes de contrato.

## Automações

- Backup diário.
- Alerta de estoque baixo.
- Fechamento de caixa pendente.
- Relatório diário por email.
- Rotina de integridade do banco.

## IA

Possibilidades futuras:

- Previsão de reposição de estoque.
- Sugestão de compras.
- Análise de produtos com baixa margem.
- Assistente para consulta de vendas.
- Detecção de anomalias em caixa.
