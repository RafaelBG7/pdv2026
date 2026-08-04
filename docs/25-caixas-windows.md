# 25 - Caixa atual e caixas anteriores no Windows

## Objetivo

Este documento descreve o módulo **Caixa** do cliente Girofy Windows (WPF), incluindo a
navegação interna, os estados da interface, a consulta de caixas encerrados, o detalhe
financeiro e a linha do tempo expansível de vendas.

O cliente Windows não possui banco local e não calcula o fechamento como fonte de verdade.
Todas as informações são obtidas da API autenticada do Girofy, que aplica isolamento por
adega, permissões e regras financeiras no servidor.

## Experiência de uso

A tela possui uma navegação secundária no topo, composta por duas opções:

| Opção | Finalidade | Estado inicial |
|---|---|---|
| `Caixa atual` | Abrir, acompanhar e fechar o caixa em operação. | Selecionada ao entrar na tela ou trocar de sessão. |
| `Caixas anteriores` | Consultar os dez caixas fechados mais recentes e seus detalhes. | Selecionada automaticamente após um fechamento bem-sucedido. |

A opção ativa reutiliza o padrão visual global do Windows: superfície elevada, borda
semântica informativa, tipografia e botões definidos nos recursos compartilhados. A troca
de opção acontece no próprio `ViewModel`, sem nova navegação de página e sem nova consulta
à API.

Mensagens antigas de sucesso ou erro são limpas ao trocar de opção, evitando que um aviso
de uma operação anterior seja interpretado como pertencente ao conteúdo recém-aberto.

## Caixa atual

Quando não existe caixa aberto, a tela apresenta o formulário de abertura com valor inicial.
Quando existe caixa aberto, apresenta seus dados operacionais, os indicadores financeiros
autorizados e o formulário de fechamento.

O fechamento exige o valor contado. O servidor valida esse valor contra:

```text
valor esperado = valor inicial + total vendido no caixa
```

Em caso de divergência, o caixa continua aberto e o valor digitado é preservado para
correção. Após o fechamento confirmado, o campo é limpo e a interface muda para
`Caixas anteriores`, onde o caixa recém-encerrado aparece na lista retornada pela API.

## Caixas anteriores

A lista usa uma `DataGrid` somente leitura e apresenta:

- número do caixa;
- data e hora de abertura;
- data e hora de fechamento;
- responsável;
- quantidade de vendas;
- total vendido, quando permitido;
- status.

A grade habilita virtualização de linhas e reciclagem de elementos visuais para reduzir
alocação e renderização. Quando não há registros, a grade é ocultada e um estado vazio
explica que os caixas encerrados aparecerão naquele espaço.

O resumo inicial contém no máximo os dez caixas fechados mais recentes. Essa limitação é
do contrato atual da API; paginação, busca por período e filtros históricos ainda não fazem
parte deste fluxo.

## Abertura do detalhe

Ao selecionar uma linha, o `SelectionChanged` solicita o detalhe daquele caixa. A lista
resumida não transporta antecipadamente todas as vendas, itens e pagamentos. Esse desenho
mantém a entrada na tela leve e transfere os dados detalhados somente quando necessários.

Durante a solicitação, a interface mostra `Carregando detalhes do caixa...`. O botão
`Atualizar detalhe` permite repetir a consulta do registro selecionado. O botão `Fechar`
remove o painel de detalhe da tela sem alterar dados no servidor.

O painel apresenta os dados consolidados disponíveis, incluindo:

- abertura e fechamento;
- responsável e status;
- valor inicial e valor final;
- total vendido e valor esperado;
- diferença de fechamento;
- quantidade de vendas e ticket médio;
- totais por Dinheiro, Pix, Débito e Crédito.

Campos financeiros são exibidos somente quando a API informa
`can_view_financials = true`, derivado da permissão de relatórios do usuário.

## Linha do tempo de vendas

O detalhe contém uma linha do tempo cronológica das vendas vinculadas ao caixa. Cada venda
é apresentada em um `Expander`: o cabeçalho mantém a leitura rápida e o conteúdo completo
só é renderizado visualmente quando o usuário expande a venda.

O cabeçalho identifica, conforme dados disponíveis:

- número e horário da venda;
- vendedor;
- status;
- total final;
- resumo das formas de pagamento.

Ao expandir, são apresentados os produtos vendidos, quantidades, valores, descontos e os
pagamentos associados. Se o caixa não possuir vendas, a tela apresenta um estado vazio
específico para a linha do tempo.

## Contratos da API

### Resumo

```http
GET /api/v1/cash-registers/summary
Authorization: Bearer <access_token>
```

Retorna `current_register`, `recent_registers` e permissões. É chamado ao inicializar ou
atualizar o módulo e após as operações de abertura e fechamento.

### Detalhe sob demanda

```http
GET /api/v1/cash-registers/{cash_register_id}
Authorization: Bearer <access_token>
```

Retorna o caixa solicitado e sua linha do tempo. O backend rejeita registros inexistentes
ou pertencentes a outra adega.

### Operações

```http
POST /api/v1/cash-registers/open
POST /api/v1/cash-registers/close
```

O servidor serializa as operações, impede dois caixas abertos na mesma adega e valida o
fechamento de forma transacional. Consulte `docs/09-api.md` para payloads e erros.

## Arquitetura no cliente

| Responsabilidade | Arquivo |
|---|---|
| Estado, comandos, validações locais e chamadas assíncronas | `desktop_wpf/src/Girofy.Application/ViewModels/CashRegisterViewModel.cs` |
| Layout, estilos, bindings, estados vazios e expanders | `desktop_wpf/src/Girofy.Desktop/Views/CashRegisterView.xaml` |
| Seleção da grade e acionamento do detalhe | `desktop_wpf/src/Girofy.Desktop/Views/CashRegisterView.xaml.cs` |
| Contrato abstrato do cliente HTTP | `desktop_wpf/src/Girofy.Application/Abstractions/IGirofyApiClient.cs` |
| Implementação HTTP | `desktop_wpf/src/Girofy.Infrastructure/Api/GirofyApiClient.cs` |
| Testes do estado e dos comandos | `desktop_wpf/tests/Girofy.UnitTests/CashRegisterViewModelTests.cs` |

As propriedades `IsCurrentRegisterTabSelected` e `IsPreviousRegistersTabSelected` controlam
a visibilidade das duas áreas. `HasRecentRegisters` e `HasNoRecentRegisters` alternam entre
a grade e o estado vazio. `IsDetailLoading`, `HasDetail`, `HasTimeline` e `HasNoTimeline`
representam os estados do detalhe sem lógica de negócio no code-behind.

As respostas assíncronas só são aplicadas se o token da sessão ainda for o mesmo usado no
início da chamada. Uma troca ou encerramento de sessão limpa snapshot, seleção, detalhe,
campos, mensagens e restaura `Caixa atual` como opção ativa.

## Permissões e segurança

- `can_manage_cash_register` controla a disponibilidade do módulo e das operações.
- `can_view_reports` controla a exposição de valores financeiros no servidor.
- O identificador da adega nunca é aceito da interface; ele é obtido do token.
- O cliente não acessa MySQL diretamente.
- Erros inesperados são convertidos em mensagens seguras, sem detalhes internos.
- Uma sessão alterada durante uma resposta assíncrona impede a aplicação de dados antigos.

## Estados previstos

| Estado | Resposta visual |
|---|---|
| Sem caixa aberto | Formulário para informar o valor inicial. |
| Caixa aberto | Resumo operacional, indicadores autorizados e fechamento. |
| Sem caixas anteriores | Card de estado vazio; grade oculta. |
| Com caixas anteriores | Grade resumida virtualizada. |
| Detalhe carregando | Aviso informativo de carregamento. |
| Caixa selecionado com vendas | Resumo financeiro e linha do tempo expansível. |
| Caixa selecionado sem vendas | Resumo do caixa e estado vazio da linha do tempo. |
| Erro de API ou rede | Mensagem segura; dados digitados são preservados quando aplicável. |
| Sessão encerrada ou trocada | Dados do módulo são limpos e a opção inicial é restaurada. |

## Testes automatizados

Os testes do `CashRegisterViewModel` cobrem:

- carga do caixa atual e preenchimento do valor esperado;
- conversão monetária no formato brasileiro;
- abertura bem-sucedida;
- preservação do caixa e do valor digitado quando o fechamento falha;
- limpeza do campo e seleção de `Caixas anteriores` após fechamento bem-sucedido;
- navegação entre as duas opções internas;
- detecção de lista de caixas anteriores com conteúdo;
- carregamento do detalhe e da linha do tempo do caixa selecionado;
- limpeza dos dados após encerramento da sessão.

Comando de validação em ambiente com .NET SDK:

```bash
dotnet test desktop_wpf/tests/Girofy.UnitTests/Girofy.UnitTests.csproj
```

## Critérios de aceite manual

1. Entrar em Caixa e confirmar que `Caixa atual` inicia selecionado.
2. Alternar entre as duas opções e confirmar que somente o conteúdo escolhido aparece.
3. Abrir um caixa, registrar vendas com formas de pagamento diferentes e fechá-lo.
4. Confirmar a troca automática para `Caixas anteriores` após o fechamento.
5. Selecionar o caixa encerrado e conferir totais, pagamentos e quantidade de vendas.
6. Expandir vendas da linha do tempo e conferir itens e pagamentos.
7. Testar um caixa sem vendas e confirmar o estado vazio da linha do tempo.
8. Testar um usuário sem permissão financeira e confirmar que valores sensíveis não aparecem.
9. Trocar ou encerrar a sessão durante o uso e confirmar que nenhum dado da sessão anterior permanece.

## Limitações conhecidas

- o resumo histórico está limitado aos dez caixas encerrados mais recentes;
- não há paginação ou filtro por intervalo no contrato atual;
- sangria, suprimento, estorno e reabertura de caixa continuam fora do escopo;
- a compilação e os testes WPF exigem Windows ou ambiente com SDK .NET compatível;
- a publicação do ZIP depende da disponibilidade da cota de artefatos do GitHub Actions.
