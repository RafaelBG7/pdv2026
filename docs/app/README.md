# Girofy App Windows

O App é um cliente WPF online. Sua estrutura fica em `desktop_wpf`: Presentation/Desktop, Application/ViewModels e Infrastructure/serviços HTTP.

## Funções

- login, refresh/logout e recuperação de senha;
- dashboard, catálogo, vendas, cancelamento, caixa atual/anteriores;
- estoque, contas, relatórios, auditoria e notificações;
- equipe, perfil, senha, empresa, importação/exportação e backup;
- tema claro/escuro e preferências locais.

Tokens são protegidos localmente; dados de negócio não são persistidos como banco paralelo. Sem rede, a operação informa indisponibilidade: não existe sincronização offline. ViewModels devem cancelar/reutilizar carregamentos e nunca implementar cálculos financeiros autoritativos.

O App consome `/api/v1`; uma mudança incompatível exige nova versão de API, não alteração silenciosa. Consulte [paridade](../FEATURE_PARITY.md).
