# Notificações — Web, Windows e e-mail

## Objetivo

O Girofy mantém uma fonte persistente de notificações por adega e entrega a mesma informação operacional no aplicativo Windows. Os alertas de e-mail já configurados na Web continuam sendo a fonte de preferências e destinatários, mas agora o SMTP é executado fora do tempo da requisição para não atrasar telas, vendas ou atualizações do caixa.

## Regras aproveitadas da versão Web

| Evento | Categoria | Severidade no Windows | E-mail |
|---|---|---:|---:|
| Produto esgotado | Estoque | Crítica | Habilitado por padrão |
| Estoque igual ou abaixo do mínimo | Estoque | Atenção | Configurável |
| Conta vence em até três dias | Contas | Informação | Somente no aplicativo |
| Conta vence hoje | Contas | Atenção | Habilitado por padrão |
| Conta vencida | Contas | Crítica | Habilitado por padrão |
| Assinatura vence em até três dias | Assinatura | Atenção | Habilitado por padrão na Web |

Movimentações de estoque também geram alertas persistentes para estoque negativo e ajustes manuais grandes. Quando a condição deixa de existir, a notificação operacional é resolvida e deixa de aparecer na lista ativa.

## Persistência e isolamento

As tabelas `notifications` e `notification_preferences` pertencem ao banco do tenant. Toda consulta exige `company_id` e limita notificações pessoais ao usuário autenticado; notificações sem `user_id` são visíveis para os usuários daquela adega. A restrição única `(company_id, deduplication_key)` impede repetição do mesmo evento.

Estados suportados:

- não lida ou lida, com data da leitura;
- dispensada, com data da ação;
- resolvida automaticamente quando a condição operacional termina;
- situação do envio de e-mail e metadados mínimos do evento.

## API usada pelo Windows

- `GET /api/v1/notifications`: lista paginada, total e contador de não lidas;
- `GET /api/v1/notifications/unread-count`: contador leve para o sino;
- `PUT /api/v1/notifications/{id}/read`: marca uma notificação como lida;
- `PUT /api/v1/notifications/read-all`: marca todas como lidas e grava auditoria;
- `PUT /api/v1/notifications/{id}/dismiss`: dispensa uma notificação;
- `GET|PUT /api/v1/notifications/preferences`: preferências do usuário e validação de destinatários.

Filtros disponíveis: categoria, severidade, estado de leitura, período, texto, página e tamanho da página. Antes da leitura, o backend materializa os alertas atuais de estoque e contas usando as mesmas regras da Web.

## Experiência no Windows

O cabeçalho possui um sino com badge de não lidas. A central contém busca, filtros por categoria e severidade, atualização manual, leitura individual, leitura de todas e dispensa. O carregamento trata os estados de espera, vazio, erro e nova tentativa.

Após autenticação, o aplicativo atualiza a central e inicia polling a cada 60 segundos. O polling possui cancelamento por sessão: sair ou trocar de usuário interrompe a tarefa anterior, limpa os dados e evita requisições concorrentes antigas. As chamadas são assíncronas e não bloqueiam a interface.

## Entrega por e-mail

As opções continuam em **Configurações > Alertas por e-mail** na versão Web. Cada tipo possui habilitação e lista de destinatários. Se a lista estiver vazia, o alerta não é enviado.

O servidor aplica três proteções:

1. janela de verificação por empresa para evitar varreduras a cada renderização;
2. chave persistente em `email_alert_deliveries`, impedindo reenvio do mesmo evento;
3. executor de segundo plano com até dois workers, impedindo que latência ou falha SMTP bloqueie a resposta Web.

Falhas de autenticação e transporte SMTP são registradas no log sem interromper a operação principal. Em testes, a entrega permanece síncrona para tornar as asserções determinísticas.

## Configuração operacional

O ambiente precisa fornecer servidor SMTP, porta, usuário, senha, remetente e política TLS aceitos pelo provedor. Recomenda-se usar credencial exclusiva do aplicativo, limitar o remetente ao domínio autorizado e monitorar os logs de falha. Alterar destinatários exige a permissão de configurações.

## Validação e evolução

Há cobertura automatizada para isolamento entre empresas, paginação/listagem, leitura, dispensa, deduplicação, preferências, materialização de alertas de estoque/contas e envio único por e-mail. A evolução natural é adicionar toast nativo do Windows e administrar todas as preferências de e-mail diretamente no desktop; a central e os contratos já foram preparados para isso.
