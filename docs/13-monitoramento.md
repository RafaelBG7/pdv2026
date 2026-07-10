# 13 - Monitoramento

## Status Atual

O sistema possui monitoramento básico por logs de erro e alertas operacionais na interface.

Implementado:

- Logs detalhados de erro em `logs/errors.log`.
- Eventos externos, como rotas inexistentes anônimas, em `logs/security.log`.
- Visualização dos logs recentes no painel master.
- Botão para limpar logs no painel master.
- Auditoria de ações críticas em `audit_logs`.
- Consulta de auditoria operacional em `/auditoria`.
- Consulta de auditoria central em `/master/auditoria`.
- Notificações de estoque baixo, produto sem estoque e contas a pagar.
- Mensagens visuais com `flash`.

Ainda não implementado:

- Métricas externas.
- Monitoramento de disponibilidade.
- Alertas por WhatsApp.
- Dashboard técnico de performance.

## Logs de Erro

Arquivo:

```text
logs/errors.log
```

O log registra:

- Código HTTP.
- Exceção.
- Rota/endpoint.
- Método.
- Caminho.
- Query string.
- Dados de formulário com campos sensíveis mascarados.
- Usuário autenticado.
- Duração da requisição.
- `X-Request-ID`.

Parâmetros sensíveis são mascarados antes da gravação e a URL bruta com query string
não é persistida. Exceções não tratadas são registradas uma única vez com traceback.

O master do sistema consegue ver os erros recentes em `/master/logs`. O botão
`Limpar logs` limpa `errors.log` e `security.log`.

## Auditoria de Ações

A auditoria complementa os logs de erro. Ela registra eventos de negócio em banco de
dados, com usuário, perfil, rota, método, IP, request id, entidade afetada e valores
antigos/novos sanitizados.

Eventos cobertos:

- Login, logout e falha de login.
- Cadastro de empresa e usuário.
- Geração, uso e alteração de key/assinatura.
- Criação, edição, ativação/inativação e exclusão de produto.
- Criação, edição e exclusão de categoria.
- Importação e exportação de dados.
- Abertura e fechamento de caixa.
- Venda concluída.
- Contas a pagar criadas, pagas e reabertas.
- Entrada e ajuste de estoque.

## Alertas Operacionais

As notificações aparecem no topo da interface:

- Produto sem estoque.
- Produto com estoque igual ou abaixo do estoque mínimo.
- Conta vencida.
- Conta vencendo hoje.
- Conta vencendo em até 3 dias.

As notificações são filtradas pela adega atual.

## Alertas por E-mail

Além das notificações internas, a aba `Configurações > Alertas` permite ativar envio por e-mail e definir destinatários por tipo de alerta.

Tipos atuais:

- Produto esgotado.
- Estoque baixo.
- Conta vence hoje.
- Conta vencida.
- Assinatura perto do vencimento.

O sistema registra cada alerta enviado para evitar disparos repetidos enquanto a situação não mudar.

## Métricas de Negócio Disponíveis

O próprio sistema já mostra:

- Total vendido no dia.
- Lucro do dia.
- Ticket médio.
- Status do caixa.
- Produtos com estoque baixo.
- Contas vencidas ou próximas.
- Produtos mais vendidos.
- Vendas por período em relatório e gráfico.

## O Que Monitorar em Produção

Aplicação:

- Quantidade de erros 500.
- Tempo médio de resposta.
- Falhas de login.
- Tentativas de acesso sem permissão.

Banco:

- Tamanho do banco central.
- Tamanho dos bancos por adega.
- Tempo de consulta em relatórios.
- Falhas de conexão MySQL.

Negócio:

- Caixas abertos há muito tempo.
- Estoque crítico.
- Vendas canceladas ou bloqueadas.
- Contas vencidas.

Backup:

- Último backup com sucesso.
- Falhas de backup.
- Tamanho dos arquivos gerados.
- Teste periódico de restauração.

## Próximo Passo Recomendado

Evoluir a auditoria para eventos ainda não existentes no produto, como cancelamento de
venda, estorno, sangria, suprimento de caixa e aprovações por senha.
