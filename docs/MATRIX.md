# Matriz resumida Web, App e Backend

Legenda: `Completo`, `Parcial`, `N/A` (não pertence à plataforma) e `Pendente`.

| Domínio | Web | Windows | Backend/API | Observação |
|---|---|---|---|---|
| Login, logout e sessão | Completo | Completo | Completo | Web usa cookie; App usa access/refresh token protegido por DPAPI. |
| Cadastro de adega e verificação de e-mail | Completo | Parcial | Completo | Cadastro permanece orientado pela Web; App possui recuperação de senha. |
| Dashboard | Completo | Completo | Completo | Mesma fonte de dados por tenant. |
| Produtos e categorias | Completo | Completo | Completo | CRUD, filtros, kits, status e estoque mínimo. |
| Venda e pagamentos | Completo | Completo | Completo | Ambos usam `sale_service.create_sale`, Decimal, locks e idempotência. |
| Cancelamento/estorno interno | Completo | Completo | Completo | Estoque é devolvido de forma auditável; não há estorno em adquirente. |
| Caixa atual e anteriores | Completo | Completo | Completo | Abertura/fechamento usam o mesmo serviço transacional. |
| Estoque e movimentações | Completo | Completo | Completo | Baixa de venda, entrada, ajuste, filtros e auditoria. |
| Contas a pagar | Completo | Completo | Completo | Criar, pagar, reabrir e filtrar. |
| Relatórios | Completo | Completo | Completo | Resumo e produto; representação visual difere por plataforma. |
| Auditoria | Completo | Completo | Completo | Painel master possui escopo adicional. |
| Notificações | Completo | Completo | Completo | Web e App exibem alertas; backend também entrega e-mail configurável. |
| Equipe e configurações | Completo | Completo | Completo | Respeita permissões e tenant. |
| Importação/exportação/backup | Completo | Completo | Completo | Restauração guiada continua pendente. |
| Assinatura e ativação | Completo | Parcial | Completo | App ativa assinatura; administração comercial fica na Web. |
| Painel SaaS master | Completo | N/A | Completo | Função deliberadamente exclusiva da Web. |
| Operação offline/sincronização | N/A | Pendente | N/A | Não faz parte da arquitetura atual; o App é online. |

Detalhes, contratos, evidências e pendências: [FEATURE_PARITY.md](FEATURE_PARITY.md).
