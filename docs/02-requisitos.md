# 02 - Requisitos

## Requisitos Funcionais

| ID | Requisito | Status | Evidência |
|---|---|---|---|
| RF001 | Realizar login/logout | Implementado | `/login`, `/logout` em `app/routes/auth.py`. |
| RF002 | Cadastrar nova adega | Implementado | Aba Cadastrar em `app/templates/login.html`. |
| RF003 | Confirmar e-mail no cadastro | Implementado | `/verify-email` e `EmailVerificationCode`. |
| RF004 | Recuperar senha por e-mail | Implementado | `/forgot-password`, `/reset-password/<token>` e `PasswordResetToken`. |
| RF043 | Trocar e-mail com confirmação no e-mail antigo | Implementado | `EmailChangeRequest` e `/confirmar-troca-email/<token>`. |
| RF005 | Cadastrar com key de ativação | Implementado | `ActivationKey` e fluxo de cadastro. |
| RF006 | Cadastrar sem key e bloquear uso | Implementado | Opção "Não tenho key" e redirecionamento para `/assinatura`. |
| RF007 | Criar banco separado para adega | Implementado | `app/tenant.py`. |
| RF008 | Gerenciar adegas no painel master | Implementado | `/master/adegas`. |
| RF009 | Gerar key Basic/Pro | Implementado | Configurações > Gerar key. |
| RF010 | Ver e limpar logs no master | Implementado | `/master/adegas` e `/master/logs/limpar`. |
| RF011 | Editar dados do usuário | Implementado | Configurações > Usuário. |
| RF012 | Gerenciar funcionários | Implementado | Configurações > Equipe. |
| RF013 | Buscar funcionário por nome/login/CPF | Implementado | Template e JS de sugestões. |
| RF014 | Aplicar perfis funcionário/gerente/admin | Implementado | `apply_employee_permissions()`. |
| RF015 | Configurar taxas de Pix, débito e crédito | Implementado | Configurações > Financeiro. |
| RF016 | Alternar tema claro/escuro | Implementado | Configurações > Aparência. |
| RF017 | Listar, filtrar e ordenar produtos | Implementado | `/catalogo/produtos`. |
| RF018 | Cadastrar, editar, inativar e excluir produto | Implementado | Rotas em `catalog.py`. |
| RF019 | Controlar estoque mínimo | Implementado | Campo `min_stock_quantity` e notificações. |
| RF020 | Configurar produto kit | Implementado | Campos `is_kit` e produto base. |
| RF021 | Importar produtos por CSV/XLSX | Implementado | Configurações > Importação. |
| RF022 | Baixar modelo de planilha | Implementado | `auth.import_template_download`. |
| RF023 | Cadastrar e editar categorias por adega | Implementado | `/catalogo/categorias`. |
| RF024 | Abrir caixa | Implementado | `/caixa/abrir`. |
| RF025 | Fechar caixa com validação exata | Implementado | `/caixa/fechar`. |
| RF026 | Ver detalhes de caixas anteriores | Implementado | `/caixa/<id>`. |
| RF027 | Bloquear venda sem caixa aberto | Implementado | `new_sale()`. |
| RF028 | Registrar venda com vários produtos | Implementado | `/vendas/nova`. |
| RF029 | Finalizar venda por clique e F2 | Implementado | Tela de venda e JS. |
| RF030 | Aplicar desconto com F3 | Implementado | `discount_amount`. |
| RF031 | Aceitar dinheiro, Pix, débito e crédito | Implementado | Modelo `Payment`. |
| RF032 | Permitir múltiplas formas de pagamento | Implementado | Lista de pagamentos. |
| RF033 | Preservar pedido quando há erro | Implementado | Renderização mantém estado do formulário. |
| RF034 | Calcular lucro por produto/venda/caixa | Implementado | `profit_amount` e relatórios. |
| RF035 | Gerar relatórios por período | Implementado | `/relatorios`. |
| RF036 | Gerar gráfico de vendas | Implementado | `build_chart_buckets()`. |
| RF037 | Gerenciar contas a pagar | Implementado | `/contas-a-pagar`. |
| RF038 | Notificar vencimentos | Implementado | `inject_user()` em `app/__init__.py`. |
| RF044 | Enviar alertas críticos por e-mail | Implementado | Configurações > Alertas e `EmailAlertSetting`. |
| RF039 | Fazer backup manual/automático | Implementado | `app/backup.py`. |
| RF040 | Exportar dados em CSV | Implementado | `/exportacoes/<tipo>`. |
| RF041 | API pública JSON | Não implementado | Rotas atuais são HTML/formulário. |
| RF042 | Auditoria de ações | Não implementado | Há log de erro, mas não trilha de ações. |

## Requisitos Não Funcionais

| Área | Requisito | Status | Observações |
|---|---|---|---|
| Isolamento | Dados de cada adega separados | Implementado | Banco MySQL por adega. |
| Segurança | Senhas com hash | Implementado | Werkzeug `scrypt`. |
| Segurança | Bloqueio de tentativas de login | Implementado parcial | Limite simples em memória para ambiente local/controlado. |
| Segurança | Permissão no backend | Implementado | `permission_required`. |
| Segurança | Bloqueio por assinatura/key | Implementado | `company_requires_activation()`. |
| Segurança | CSRF | Não implementado | Recomendado Flask-WTF ou proteção equivalente. |
| Disponibilidade | Execução local | Implementado | `python app.py` na porta 5001. |
| Backup | Dump SQL por adega | Implementado | Pasta `backups/`. |
| Logs | Logs detalhados de erro | Implementado | `logs/errors.log`. |
| Escalabilidade | Multiempresa | Implementado inicial | Banco por tenant, sem fila ou balanceamento. |
| Manutenibilidade | Organização modular | Implementado | Blueprints, modelos e serviços. |
| Testabilidade | Testes automatizados | Implementado | `unittest discover`. |

## Premissas

- MySQL instalado e rodando.
- Cada adega possui seu próprio banco operacional.
- Usuário master do sistema é separado do admin da adega.
- Planos Basic/Pro ainda são estéticos/comerciais, sem cobrança real integrada.
- A aplicação é server-side e usa sessões de navegador.

## Fora do Escopo Atual

- Emissão fiscal.
- TEF real.
- Cobrança online de assinatura.
- API pública.
- Auditoria completa de ações.
- Controle avançado de compras/fornecedores.
