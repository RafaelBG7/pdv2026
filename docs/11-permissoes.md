# 11 - Permissões

## Visão Geral

O sistema possui permissões por perfil e bloqueio no backend usando `permission_required`.

Arquivos principais:

- `app/models/user.py`
- `app/permissions.py`
- `app/routes/auth.py`
- `app/routes/catalog.py`
- `app/routes/main.py`
- `app/templates/settings/index.html`

## Perfis

| Perfil | Código | Uso |
|---|---|---|
| Master do sistema | `master` | Usuário global que gerencia todas as adegas, logs, keys e painel master. |
| Admin da adega | `admin` | Dono/master da adega. Pode executar todas as ações da adega. |
| Gerente | `manager` | Pode operar quase tudo, mas não deve acessar financeiro/plano sensível. |
| Funcionário | `operator` | Pode vender, abrir caixa e acessar configurações pessoais. |

Observação: o sistema agora permite mais de um `admin` por adega.

## Permissões Técnicas

As permissões ficam no modelo `User`:

| Campo | Significado |
|---|---|
| `can_view_products` | Ver produtos. |
| `can_manage_products` | Criar, editar, importar e alterar produtos. |
| `can_manage_categories` | Criar, editar e excluir categorias. |
| `can_manage_sales` | Registrar e consultar vendas. |
| `can_manage_cash_register` | Abrir, fechar e consultar caixa. |
| `can_view_reports` | Acessar relatórios. |
| `can_manage_payables` | Gerenciar contas a pagar. |
| `can_manage_settings` | Acessar configurações permitidas ao perfil. |
| `can_view_stock_movements` | Consultar histórico de movimentações de estoque. |
| `can_manage_stock` | Registrar entrada e ajuste manual de estoque. |
| `can_view_audit_logs` | Consultar auditoria da adega. |

`master` e `admin` retornam verdadeiro para todas as permissões em `User.has_permission()`.

## Matriz de Acesso

| Área | Master sistema | Admin adega | Gerente | Funcionário |
|---|---:|---:|---:|---:|
| Painel master | Sim | Não | Não | Não |
| Gerar key | Sim | Não | Não | Não |
| Logs do sistema | Sim | Não | Não | Não |
| Dashboard | Sim | Sim | Sim | Sim |
| Produtos - ver | Sim | Sim | Sim | Sim |
| Produtos - alterar | Sim | Sim | Sim | Não |
| Categorias | Sim | Sim | Sim | Não |
| Venda | Sim | Sim | Sim | Sim |
| Caixa | Sim | Sim | Sim | Sim |
| Estoque - histórico | Sim | Sim | Sim | Não |
| Estoque - entrada/ajuste | Sim | Sim | Sim | Não |
| Relatórios | Sim | Sim | Sim | Não |
| Auditoria da adega | Sim | Sim | Sim | Não |
| Contas a pagar | Sim | Sim | Sim | Não |
| Configurações pessoais | Sim | Sim | Sim | Sim |
| Equipe | Sim | Sim | Não | Não |
| Financeiro/taxas | Sim | Sim | Não | Não |
| Importação | Sim | Sim | Não | Não |
| Exportação | Sim | Sim | Não | Não |
| Plano/assinatura | Sim | Sim | Não | Não |

## Funcionário

O funcionário comum deve ter acesso limitado:

- Pode realizar venda.
- Pode abrir/operar caixa.
- Pode ver produtos quando necessário para venda.
- Pode alterar apenas configurações pessoais.
- Não pode editar produto, categoria ou preço.
- Não vê equipe, financeiro, plano, importação ou exportação.

## Gerente

O gerente é operacional:

- Pode vender, abrir caixa, ver relatórios e gerenciar catálogo.
- Pode consultar auditoria operacional e movimentar estoque, conforme permissões padrão.
- Não deve acessar financeiro sensível, plano/assinatura ou gestão avançada da equipe.

## Admin da Adega

O admin é o responsável pela adega:

- Pode contratar funcionários.
- Pode editar perfis e CPF.
- Pode ativar/inativar usuários.
- Pode importar/exportar dados.
- Pode configurar taxas de Pix, débito e crédito.
- Pode configurar backups.
- Pode consultar auditoria da adega.
- Pode registrar entrada e ajuste de estoque.

Proteções importantes:

- O admin não deve conseguir inativar a si mesmo como último acesso prático.
- CPF duplicado é bloqueado dentro da mesma adega.
- Username continua único no sistema.

## Master do Sistema

O master do sistema:

- Acessa `/master/adegas`.
- Pode entrar em qualquer adega para suporte.
- Gera keys avulsas ou vinculadas a uma adega.
- Vê e limpa logs de erro.
- Vê auditoria central em `/master/auditoria`.
- Pode editar/inativar/excluir adegas.

Esse usuário não representa o dono de uma adega específica.
