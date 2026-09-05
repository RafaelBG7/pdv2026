# Importação de relatórios históricos

## Escopo

A funcionalidade importa resumos diários de vendas vindos de outro sistema. Os registros ficam em `historical_daily_reports` e nunca criam vendas, itens, pagamentos, movimentações de estoque, comissões, contas a receber ou lançamentos de caixa.

A interface fica em **Configurações > Importação > Relatórios históricos** e só aparece em desenvolvimento ou homologação para administradores. Produção responde `404` para todos os endpoints do recurso.

## Contrato do arquivo

O modelo oficial é `app/static/files/modelo_importacao_relatorios_skygest.xlsx`. A aba obrigatória é `Importacao_Relatorios`, com os cabeçalhos abaixo na ordem exata:

```text
data, quantidade_vendas, faturamento, lucro_bruto, ticket_medio, origem
```

São aceitos XLSX sem macros e CSV UTF-8. A importação aceita datas Excel, `AAAA-MM-DD` e `DD/MM/AAAA`, além de valores monetários numéricos ou no padrão brasileiro. Fórmulas e conteúdo executável são recusados. O limite global de upload é 8 MiB e o limite específico é 10.000 linhas não vazias.

## Fluxo e endpoints Web

- `GET /relatorios/importacao/`: upload, histórico dos últimos 50 lotes e resultado.
- `GET /relatorios/importacao/modelo`: download byte a byte do modelo oficial.
- `POST /relatorios/importacao/previsualizar`: valida o arquivo e cria uma prévia temporária, sem gravar dados históricos.
- `POST /relatorios/importacao/confirmar`: revalida conflitos e grava o lote em uma transação.
- `GET /relatorios/importacao/erros/<token>.csv`: relatório por linha, campo, valor e motivo.

A prévia temporária é vinculada ao `company_id` e ao `user_id`, expira em uma hora e é removida após a confirmação. A confirmação possui chave idempotente única por empresa para impedir duplicação por clique duplo ou repetição da requisição.

## Banco de dados

As migrations `central_0010` e `tenant_0010` criam:

- `historical_report_import_batches`: arquivo, hash SHA-256, usuário, período, estratégia, contadores, status e chave idempotente;
- `historical_daily_reports`: empresa, data, quantidade, faturamento `NUMERIC(18,2)`, lucro opcional, ticket calculado, origem, lote, usuário e timestamps.

Há unicidade por `company_id` e `report_date`. O backend sempre obtém a empresa da sessão autenticada.

## Cálculos dos relatórios

Nas consultas de dashboard e relatório geral, o SkyGest soma vendas reais e resumos históricos por período. O ticket médio é sempre `SUM(faturamento) / SUM(quantidade_vendas)`. Gráficos diários e mensais somam as duas fontes por data, sem criar linhas de venda fictícias.

Pagamentos, produtos, categorias, vendas recentes, caixa e estoque continuam usando apenas vendas reais. Se qualquer resumo do período não tiver lucro bruto, o lucro consolidado aparece como indisponível, evitando apresentar um valor parcial como completo.

## Validação manual em homologação

1. Entrar como administrador e abrir **Configurações > Importação**.
2. Baixar o modelo e conferir as duas abas e os seis cabeçalhos.
3. Preencher datas sem vendas reais, enviar e conferir a prévia, totais, avisos e ticket calculado.
4. Confirmar com **Ignorar registros existentes** e conferir o lote no histórico.
5. Reenviar uma data alterada com **Atualizar registros existentes**.
6. Abrir Dashboard e Relatórios nos períodos diário, mensal e anual e conferir os totais.
7. Tentar uma data que já possua venda SkyGest e confirmar que a linha é bloqueada.
8. Conferir que estoque, caixa, pagamentos e listagem de vendas não mudaram.

Produção e geração de versão permanecem bloqueadas até autorização explícita após este teste manual.
