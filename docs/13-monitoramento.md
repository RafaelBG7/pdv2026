# 13 - Monitoramento

## Status Atual

Monitoramento dedicado não está implementado.

O sistema possui:

- Mensagens visuais para usuário via `flash`.
- Alertas de estoque baixo na interface.
- Logs padrão do Flask/servidor em execução.

O sistema não possui:

- Logs estruturados.
- Métricas.
- Alertas externos.
- Monitoramento de disponibilidade.
- Rastreamento de erro.
- Auditoria.

## Logs Recomendados

Eventos a registrar:

- Login com sucesso.
- Login inválido.
- Logout.
- Criação, edição, inativação e exclusão de produto.
- Criação, edição e exclusão de categoria.
- Abertura e fechamento de caixa.
- Tentativa de fechamento com divergência.
- Venda finalizada.
- Venda bloqueada por estoque insuficiente.
- Venda bloqueada por pagamento insuficiente.
- Alteração de senha.
- Erros 500.

Campos recomendados:

- Data/hora.
- Usuário.
- IP.
- Rota.
- Ação.
- Entidade.
- ID da entidade.
- Resultado.
- Mensagem.

## Métricas Recomendadas

Aplicação:

- Tempo de resposta por rota.
- Taxa de erros 4xx e 5xx.
- Requisições por minuto.
- Usuários ativos.

Banco:

- Tamanho do arquivo SQLite.
- Tempo médio de consulta.
- Erros de lock.

Negócio:

- Vendas por período.
- Total vendido.
- Lucro.
- Ticket médio.
- Produtos sem estoque.
- Divergências de caixa.

Infraestrutura:

- CPU.
- Memória.
- Disco.
- Disponibilidade.

## Alertas Recomendados

- Aplicação indisponível.
- Erro 500 recorrente.
- Banco sem permissão de escrita.
- Disco com pouco espaço.
- Backup falhando.
- Caixa com divergência.
- Produto crítico sem estoque.

## Auditoria

Status: não implementada.

Tabela recomendada:

```text
audit_logs
- id
- user_id
- action
- entity_type
- entity_id
- before_data
- after_data
- ip_address
- created_at
```

## Health Check

Não implementado.

Rota recomendada:

```text
GET /health
```

Resposta sugerida:

```json
{
  "status": "ok",
  "database": "ok"
}
```

## Backup Monitorado

Recomenda-se validar:

- Horário do último backup.
- Tamanho do backup.
- Integridade do SQLite.
- Teste periódico de restauração.
