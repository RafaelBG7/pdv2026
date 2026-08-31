# Auditoria financeira Float → Decimal/Numeric — gate 1.0

Data da revisão: 30/08/2026.

## Resultado executivo

O código financeiro autoritativo do backend foi migrado para `Decimal`, os campos
persistidos passaram para `NUMERIC`, as taxas preservam quatro casas e a API v1
serializa números decimais sem convertê-los para `float`. As migrations
`central_0009` e `tenant_0009` normalizam dados legados com `ROUND_HALF_UP`,
preservam valores altos e bloqueiam downgrade destrutivo.

O código está aprovado nos testes backend e compila integralmente em Release no
.NET 8. A promoção da versão 1.0 ainda depende de dois gates que não puderam ser
executados neste host macOS: testes WPF no runtime Windows e ensaio da migration em
uma cópia MySQL recente de homologação com backup/restauração verificados.

## Auditoria

### Ocorrências problemáticas corrigidas

- models SQLAlchemy: preços, caixa, venda, itens, pagamentos e taxas persistidos
  como `Float`;
- services: retornos financeiros convertidos para `float` e agregações/coalesces
  sem tipo decimal explícito;
- rotas Web/API: parsing, importação, relatórios, dashboard e caixa com conversões
  monetárias para `float` ou zeros binários;
- API v1: serialização padrão que não preservava `Decimal` como número JSON;
- compatibilidade de schema em `app/__init__.py`: DDL de contingência ainda criava
  colunas financeiras `FLOAT`;
- App WPF: dinheiro já usava `decimal`; a taxa configurável, porém, era reduzida a
  duas casas antes de ser enviada à API.

### Ocorrências mantidas

- percentuais visuais e razões de gráfico no backend são convertidos para `float`
  apenas depois de a agregação monetária terminar em `Decimal`;
- `retry_after`, durações e tempos de execução continuam com ponto flutuante por
  não serem valores financeiros;
- `double` no WPF permanece somente para dimensões, scroll e geometria de gráficos;
- migrations históricas continuam declarando `Float` porque representam o schema
  legado que precisa ser reproduzido antes da migration corretiva.

Quantidades de estoque e itens permanecem inteiras. Elas não foram confundidas com
valores monetários.

## Política financeira adotada

- dinheiro em Python: `Decimal`, quantizado em `0.01`;
- taxas: `Decimal`, quantizado em `0.0001`;
- arredondamento: `ROUND_HALF_UP` (`10.125 → 10.13`);
- conversão de legado: sempre por representação textual (`Decimal(str(valor))`),
  nunca `Decimal(float)`;
- dinheiro persistido: `NUMERIC(18,2)`. A capacidade maior que a sugestão
  `NUMERIC(12,2)` é intencional, pois há suporte e evidência de imports legados
  acima de R$ 9.999.999.999,99;
- taxas persistidas: `NUMERIC(8,4)`;
- frontend Web: cálculos locais continuam apenas como prévia. Produto, quantidade,
  preço, desconto, pagamentos, taxas, lucro, troco e estoque são recalculados ou
  validados no backend pelo mesmo `sale_service` usado pela API/App.

## Banco

As duas árvores recebem a mesma alteração porque o schema operacional pode existir
no central legado e em cada banco físico tenant.

| Campo | Tipo anterior | Tipo novo | Migration |
|---|---|---|---|
| `companies.pix_fee_percent` | `FLOAT` | `NUMERIC(8,4)` | `central_0009` / `tenant_0009` |
| `companies.debit_fee_percent` | `FLOAT` | `NUMERIC(8,4)` | `central_0009` / `tenant_0009` |
| `companies.credit_fee_percent` | `FLOAT` | `NUMERIC(8,4)` | `central_0009` / `tenant_0009` |
| `products.cost_price` | `FLOAT` | `NUMERIC(18,2)` | `central_0009` / `tenant_0009` |
| `products.sale_price` | `FLOAT` | `NUMERIC(18,2)` | `central_0009` / `tenant_0009` |
| `cash_registers.opening_amount` | `FLOAT` | `NUMERIC(18,2)` | `central_0009` / `tenant_0009` |
| `cash_registers.closing_amount` | `FLOAT` | `NUMERIC(18,2)` | `central_0009` / `tenant_0009` |
| `sales.total_amount` | `FLOAT` | `NUMERIC(18,2)` | `central_0009` / `tenant_0009` |
| `sales.discount_amount` | `FLOAT` | `NUMERIC(18,2)` | `central_0009` / `tenant_0009` |
| `sales.final_amount` | `FLOAT` | `NUMERIC(18,2)` | `central_0009` / `tenant_0009` |
| `sale_items.unit_price` | `FLOAT` | `NUMERIC(18,2)` | `central_0009` / `tenant_0009` |
| `sale_items.unit_cost_price` | `FLOAT` | `NUMERIC(18,2)` | `central_0009` / `tenant_0009` |
| `sale_items.total_price` | `FLOAT` | `NUMERIC(18,2)` | `central_0009` / `tenant_0009` |
| `sale_items.profit_amount` | `FLOAT` | `NUMERIC(18,2)` | `central_0009` / `tenant_0009` |
| `payments.amount` | `FLOAT` | `NUMERIC(18,2)` | `central_0009` / `tenant_0009` |
| `payables.amount` | `NUMERIC(12,2)` | `NUMERIC(18,2)` | `central_0009` / `tenant_0009` |
| `stock_movements.unit_cost` | `NUMERIC(12,2)` | `NUMERIC(18,2)` | `central_0009` / `tenant_0009` |
| `stock_movements.total_cost` | `NUMERIC(12,2)` | `NUMERIC(18,2)` | `central_0009` / `tenant_0009` |

Durante o upgrade, `NULL` financeiro vira zero e cada valor existente é quantizado
explicitamente. Exemplos cobertos: `19.899999999 → 19.90`, `10.125 → 10.13`,
`0.105 → 0.11` e `2.34567% → 2.3457%`. O downgrade para `FLOAT` lança erro porque
seria destrutivo.

## Alterações de aplicação

- helper central em `app/money.py`: conversão, quantização monetária/percentual,
  validação, formato brasileiro e serialização;
- models de empresa, produto, caixa, venda, item, pagamento, conta e movimento;
- services de venda, caixa, estoque, produto e dashboard;
- rotas Web de catálogo, vendas, caixa, relatórios, importação/exportação e taxas;
- API v1 com JSON decimal numérico via `simplejson(use_decimal=True)`;
- WPF preservando `decimal` e quatro casas nas taxas;
- documentação e heads Alembic atualizados para `central_0009`/`tenant_0009`.

## Compatibilidade

- **Dados existentes:** preservados e normalizados por política explícita; valores
  históricos altos cabem em `NUMERIC(18,2)`.
- **API `/api/v1`:** campos que já eram números continuam números JSON, sem virar
  strings e sem passar por `float`; DTOs WPF usam `decimal`.
- **Web:** aceita vírgula/ponto, mantém prévias no navegador e persiste somente o
  recálculo autoritativo do servidor.
- **App:** nenhum valor financeiro usa `double`/`float`; a solução compila em
  Release com .NET 8.
- **Tenants:** migration testada nas árvores central e tenant, inclusive tenant
  novo, existente, múltiplos tenants, idempotência e propagação de falha.
- **Relatórios/dashboard:** somas, lucro, faturamento, ticket e pagamentos usam
  `Decimal`; somente coordenadas/percentuais de apresentação viram `float`.

## Testes executados

- `python -m unittest discover`: **257 testes, OK**;
- testes novos: artefatos `0.1 + 0.2`, `0.01 × 100`, `ROUND_HALF_UP`, separadores
  CSV, taxa com quatro casas, venda de centavos, desconto/troco, JSON decimal e
  migration com dados legados/valor alto nos schemas central e tenant;
- `dotnet build desktop_wpf/Girofy.Desktop.sln -c Release`: **OK**;
- `dotnet test ... -c Release`: build dos projetos e testes **OK**, execução
  interrompida porque macOS não fornece `Microsoft.WindowsDesktop.App`;
- validação Docker Compose HML: não executada porque Docker não está disponível no
  host atual.

## Riscos e gates restantes

1. Executar `dotnet test` em runner Windows e exigir resultado verde.
2. Criar backup de uma cópia recente de produção em HML, medir o tempo/lock da
   normalização linha a linha, executar `upgrade-all` e conferir amostras/relatórios.
3. Testar restauração desse backup antes da promoção.
4. Executar health checks Web/API e smoke tests de venda, caixa e relatórios em HML.
5. Somente depois promover para produção; não realizar ajuste manual em dado real.

## Status 1.0

**NÃO APROVADO PARA 1.0**

O código backend passou integralmente e o App compila, mas a política de release
exige os testes WPF no Windows e o ensaio MySQL/HML com backup/restauração. A
aprovação deve ser alterada para **APROVADO PARA 1.0** apenas após esses dois gates
produzirem evidência verde.
