# 02 - Requisitos

## Requisitos Funcionais

| ID | Requisito | Status | Evidência |
|---|---|---|---|
| RF001 | Realizar login | Implementado | `POST /login` em `app/routes/auth.py` |
| RF002 | Realizar logout | Implementado | `GET /logout` |
| RF003 | Cadastrar novo usuário | Implementado com risco | Aba "Cadastrar" em `login.html` |
| RF004 | Criar usuário administrador inicial | Implementado | `create_app()` cria `admin/admin123` |
| RF005 | Editar dados do usuário | Implementado | `POST /configuracoes`, `form_type=profile` |
| RF006 | Editar email do usuário | Implementado | `form_type=email` |
| RF007 | Alterar senha com senha atual | Implementado | `form_type=password` |
| RF008 | Listar produtos | Implementado | `GET /catalogo/produtos` |
| RF009 | Filtrar produtos por busca, status, categoria, estoque e preço | Implementado | `catalog.products()` |
| RF010 | Ordenar produtos | Implementado | `sort` em `catalog.products()` |
| RF011 | Cadastrar produto | Implementado | `GET/POST /catalogo/produtos/novo` |
| RF012 | Editar produto | Implementado | `GET/POST /catalogo/produtos/<id>/editar` |
| RF013 | Editar produto rapidamente na listagem | Implementado | `POST /catalogo/produtos/<id>/atualizar` |
| RF014 | Ativar/inativar produto | Implementado | `POST /catalogo/produtos/<id>/alternar-status` |
| RF015 | Excluir produto | Implementado | `POST /catalogo/produtos/<id>/excluir` |
| RF016 | Cadastrar categoria | Implementado | `POST /catalogo/categorias` |
| RF017 | Listar e filtrar categorias | Implementado | `GET /catalogo/categorias` |
| RF018 | Editar categoria | Implementado | `POST /catalogo/categorias/<id>/atualizar` |
| RF019 | Excluir categoria sem produtos vinculados | Implementado | `delete_category()` bloqueia categoria em uso |
| RF020 | Criar produto kit | Implementado | Campos `is_kit`, `kit_component_product_id`, `kit_component_quantity` |
| RF021 | Calcular estoque efetivo do kit | Implementado | `Product.effective_stock_quantity` |
| RF022 | Abrir caixa | Implementado | `POST /caixa/abrir` |
| RF023 | Fechar caixa | Implementado | `POST /caixa/fechar` |
| RF024 | Impedir venda sem caixa aberto | Implementado | `new_sale()` redireciona para caixa |
| RF025 | Registrar venda | Implementado | `GET/POST /vendas/nova` |
| RF026 | Registrar venda com múltiplos itens | Implementado | Listas `product_id[]` e `quantity[]` |
| RF027 | Registrar múltiplas formas de pagamento | Implementado | `money`, `pix`, `debit`, `credit` |
| RF028 | Aplicar desconto em venda | Implementado | `discount_amount` |
| RF029 | Validar pagamento mínimo | Implementado | Bloqueia quando `paid_amount < final_amount` |
| RF030 | Calcular troco | Implementado | `change_amount` |
| RF031 | Baixar estoque automaticamente | Implementado | Decrementa produto ou base do kit |
| RF032 | Consultar vendas | Implementado | `GET /vendas` |
| RF033 | Consultar detalhe da venda | Implementado | `GET /vendas/<id>` |
| RF034 | Gerar relatório por período | Implementado | `GET /relatorios` |
| RF035 | Exibir produtos mais vendidos | Implementado | `build_sales_report()` |
| RF036 | Exibir alertas de estoque baixo | Implementado | `inject_user()` |
| RF037 | Controlar permissões por perfil | Planejado | Campo `role` existe, mas não é usado |
| RF038 | Registrar auditoria | Não implementado | Sem modelo/tabela de auditoria |
| RF039 | Recuperar senha | Não implementado | Não há rota |
| RF040 | Exportar relatórios | Não implementado | Não há endpoint/exportador |
| RF041 | API JSON pública | Não implementado | Rotas renderizam HTML |

## Requisitos Não Funcionais

| Área | Requisito | Status | Observações |
|---|---|---|---|
| Performance | Listagens devem responder bem para pequenos catálogos | Parcial | Sem paginação; consultas trazem todos os registros |
| Segurança | Senhas devem ser armazenadas com hash | Implementado | `pbkdf2:sha256` via Werkzeug |
| Segurança | Sessões protegidas por chave secreta forte | Parcial | Usa `SECRET_KEY`, mas padrão é fraco |
| Segurança | CSRF em formulários | Não implementado | `Flask-WTF` não está instalado |
| Segurança | Controle por perfil | Não implementado | Todo login acessa todas as telas |
| Disponibilidade | Execução local | Implementado | Flask dev server ou WSGI futuro |
| Backup | Backup do SQLite | Não implementado | Precisa rotina operacional |
| Escalabilidade | Suporte a múltiplos usuários simultâneos | Parcial | SQLite limita concorrência |
| Compatibilidade | Interface responsiva | Implementado | CSS com breakpoints |
| Logs | Logs estruturados | Não implementado | Apenas comportamento padrão do Flask |
| Auditoria | Histórico de ações críticas | Não implementado | Sem tabela/eventos |
| Manutenibilidade | Separação por módulos | Implementado | Blueprints, models, templates |
| Testabilidade | Testes automatizados | Implementado parcial | Cobrem rotas e regras principais |

## Premissas

- Uso inicial em rede local ou máquina local.
- Volume de dados baixo ou moderado.
- Operadores autenticados por usuário e senha.
- O banco `database/adega_jf.db` é o repositório principal de dados.

## Fora do Escopo Atual

- Emissão fiscal.
- Integração TEF.
- Impressão direta de cupom.
- Cadastro de clientes.
- Compras e fornecedores.
- Controle de contas a pagar/receber.
- Gestão multi-loja.
