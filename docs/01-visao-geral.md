# 01 - Visão Geral

O banco central e cada banco de adega possuem revisão Alembic própria, conforme [29-migracoes-versionadas.md](29-migracoes-versionadas.md).

## Propósito

O Girofy é um PDV multiadega para adegas e pequenos comércios, disponibilizado em duas
interfaces claramente separadas:

- **WEB**: produto principal executado no navegador, com backend Flask, templates Jinja e
  operação centralizada no servidor.
- **APP WINDOWS**: cliente nativo WPF/.NET conectado à API da WEB, usando os mesmos usuários,
  permissões, regras e dados. O APP não acessa o MySQL diretamente e não funciona offline.

O detalhamento funcional e visual, sempre separado entre WEB e APP WINDOWS, está em
`docs/24-estado-versoes-web-windows.md`.

O sistema centraliza:

- Vendas com múltiplos produtos e múltiplas formas de pagamento.
- Abertura, acompanhamento e fechamento de caixa.
- Produtos, categorias, kits, estoque e estoque mínimo.
- Relatórios por período e gráfico de vendas.
- Contas a pagar com alertas de vencimento.
- Notificações operacionais no topo da interface.
- Interface Girofy com tema claro/escuro, paleta não monocromática e status semânticos.
- Usuários, funcionários e permissões por perfil.
- Assinatura/key de ativação por adega.
- Movimentações de estoque rastreáveis.
- Auditoria de ações críticas.
- Banco de dados MySQL central e banco separado para cada adega.
- Painel master para gerenciar adegas, keys, logs e acesso administrativo.

## Público-alvo

- Dono da adega.
- Administrador da adega.
- Gerente operacional.
- Funcionário de caixa.
- Master do sistema/SaaS.
- Suporte técnico e desenvolvimento.

## Situação Atual

O projeto deixou de ser um PDV local simples em SQLite e passou a operar com MySQL multiadega:

- O banco central guarda empresas, usuários, assinaturas e keys.
- Cada adega tem um banco MySQL próprio para dados operacionais.
- O cadastro pode ser feito com key de ativação ou sem key, mas sem key o uso fica bloqueado.
- O master do sistema pode gerar keys, definir validade, ver logs e administrar adegas.

## Benefícios

- Separação real dos dados entre adegas.
- Fluxo de venda rápido com atalhos e autocomplete.
- Controle de permissões para funcionário, gerente e admin.
- Alertas de estoque baixo e contas a pagar.
- Relatórios e dashboard para acompanhamento diário.
- Backup por adega em arquivo SQL.
- Base pronta para evoluir para cobrança, suporte e operação SaaS.

## Status do Produto

| Área | Status | Observações |
|---|---|---|
| Login e sessão | Implementado | Flask-Login com usuário ativo/inativo e opção "Lembre de mim". |
| Cadastro de adega | Implementado | Cria empresa, usuário admin e banco da adega. |
| Assinatura/key | Implementado | Key pode ser gerada pelo master e bloqueia uso quando ausente/vencida. |
| Multiadega | Implementado | Banco central + banco MySQL separado por adega. |
| Painel master | Implementado | Gestão de adegas, logs, keys e acesso administrativo. |
| Produtos e categorias | Implementado | Filtros, edição expandida, kits, estoque mínimo e importação. |
| Vendas | Implementado | Produtos antes do pagamento, desconto, F2/F3, pagamentos mistos e troco. |
| Caixa | Implementado | Abertura obrigatória, fechamento validado e histórico. |
| Relatórios | Implementado | Diário, semanal, mensal, anual e período personalizado. |
| Dashboard | Implementado | Indicadores de venda, lucro, caixa, estoque e contas. |
| Contas a pagar | Implementado | Alertas 3 dias antes e no vencimento. |
| Notificações | Implementado | Estoque baixo, sem estoque e contas a pagar. |
| Backup | Implementado | Manual e automático por período. |
| Importação/exportação | Implementado | Importação de produtos por planilha e exportação CSV para admin. |
| Logs de erro | Implementado | Arquivo `logs/errors.log` e visualização no painel master. |
| Movimentação de estoque | Implementado | Histórico por produto, usuário, origem e saldo antes/depois. |
| Auditoria de ações | Implementado | Eventos críticos com valores sanitizados e consulta por adega/master. |
| Interface responsiva | Implementado | Paleta Girofy, filtros alinhados, menu lateral recolhível e ajustes para textos longos. |
| Deploy OCI | Implementado | Docker Compose em VM OCI Free Tier na porta pública alta `18080`. |
| Pipeline de deploy | Implementado | Workflow self-hosted recomendado para publicar sem depender do IP do desenvolvedor. |
| API para o APP Windows | Implementado | Rotas REST autenticadas atendem os módulos nativos; não deve ser confundida com API pública irrestrita. |
| APP Windows | Prévia funcional | Cliente WPF com login, dashboard, produtos, vendas, caixa, estoque, contas, relatórios, notificações, auditoria e configurações via API. |

## Pontos Fortes Atuais

- A base multiadega já está desenhada para SaaS.
- As principais rotinas de uma adega estão cobertas.
- O controle de permissões já reduz risco operacional de funcionário comum.
- O dashboard dá uma visão rápida de vendas, lucro, caixa e alertas.
- A interface usa cores semânticas para diferenciar sucesso, aviso, erro e informação.
- A arquitetura ainda é simples o suficiente para manutenção rápida.

## O Que Ainda Faz Falta

- Migrações versionadas com Alembic/Flask-Migrate.
- Monitoramento do Redis e dos eventos de rate limit em produção.
- Ampliar auditoria para cancelamento, estorno, sangria e aprovações futuras.
- Sangria e suprimento de caixa.
- Cadastro de fornecedores e compras.
- Regras comerciais reais para Basic/Pro.
- Domínio, HTTPS definitivo, backup externo e variáveis/segredos totalmente gerenciados fora do servidor.
