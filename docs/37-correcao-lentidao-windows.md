# Correção de lentidão no aplicativo Windows — 12/10/2026

## Diagnóstico confirmado no código e em reprodução local

O Windows consulta notificações ao entrar e a cada 60 segundos. A sincronização
operacional executava uma consulta por produto para resolver alertas antigos, mais
uma consulta de deduplicação por alerta ativo. Isso acrescentava trabalho ao banco
mesmo quando nada havia mudado. Kits também podiam carregar seus componentes
individualmente.

Na busca do PDV, Enter não cancelava a busca agendada pela digitação. Além disso,
a conclusão ou falha de uma busca antiga podia limpar resultados e o indicador de
carregamento de uma busca mais recente.

## Correções

- Carregar notificações operacionais em lote, restritas à adega, e resolver alertas
  em memória. O snapshot dura somente a sincronização atual; não há cache de estoque
  entre requisições. Carregar componentes de kits junto com os produtos.
- Cancelar a busca agendada ao pressionar Enter. Usar uma versão por busca para
  descartar respostas e erros antigos, inclusive quando o transporte não respeita
  o cancelamento. Apenas a busca atual encerra seu indicador de carregamento.

## Evidência de desempenho

Reprodução SQLite local com 1.000 produtos, 500 alertas ativos, segunda consulta
sem alteração de estoque:

| Medida | Antes | Depois |
|---|---:|---:|
| Comandos SQL por sincronização | 1.503 | 4 |
| Tempo observado | 146 ms | 7 ms |

Os tempos são uma amostra local, não um SLA ou medição de produção. O teste fixa
um orçamento de consultas e verifica os alertas preservados. Outro teste cobre
estoque de kits, resolução/reativação, estado de leitura, vencimento de contas e
isolamento entre adegas. Os testes Windows cobrem Enter sem requisição duplicada
e respostas/erros fora de ordem.

## Validação manual necessária em homologação

1. Usar o instalador **Homologação** do artefato do PR, conectado ao backend HML.
2. Entrar com o usuário de teste e abrir Vendas.
3. Digitar parte do nome, pressionar Enter imediatamente e selecionar o produto.
4. Trocar rapidamente o texto, inclusive apagando e repetindo o mesmo termo;
   verificar que os resultados finais correspondem ao texto atual.
5. Selecionar código de barras e quantidade; conferir que a seleção permanece.
6. Manter o aplicativo aberto por mais de um minuto e repetir buscas durante a
   atualização de notificações. Conferir Produtos, Estoque e abertura de editores.
7. Conferir alertas de estoque e contas, marcar um alerta como lido e atualizar.

A execução visual Windows exige um computador Windows. Testes automatizados e
health checks não substituem essa homologação. A promoção para main e a geração
de nova versão dependem de autorização explícita após a validação manual.
