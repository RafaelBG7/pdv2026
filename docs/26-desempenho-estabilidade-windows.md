# 26 - Desempenho e estabilidade do Girofy Windows

## Objetivo

Este capítulo define a base de estabilidade que deve ser validada antes da continuidade
de novas funcionalidades no cliente Windows. O foco inicial é impedir travamentos causados
por abertura repetida do executável, cliques rápidos e operações assíncronas obsoletas.

## Instância única

O Girofy Windows usa o mutex nomeado:

```text
Local\Girofy.Desktop.SingleInstance
```

A primeira execução adquire o mutex e inicializa host, serviços, HTTP e janela principal.
Execuções seguintes na mesma sessão do Windows são encerradas antes da construção do host.
Assim, clicar repetidamente no atalho ou executável não cria três processos concorrentes,
três conjuntos de serviços ou múltiplas cargas simultâneas da API.

O mutex é mantido durante toda a vida do processo e liberado no encerramento. Um mutex
abandonado por término inesperado é tratado como disponível na próxima inicialização.

## Proteção contra cliques repetidos

Operações de escrita e atualização ligadas a `AsyncRelayCommand` não permitem reentrância:
enquanto uma execução está ativa, `CanExecute` retorna `false`. Isso protege abertura,
fechamento, salvamento, importação, filtros e demais ações assíncronas contra duplo envio.

Consultas em que uma nova seleção deve substituir a anterior seguem outra política:

1. incrementam a versão lógica da solicitação;
2. cancelam o `CancellationTokenSource` anterior;
3. iniciam a consulta da seleção mais recente;
4. aplicam a resposta apenas se versão, seleção e sessão ainda coincidirem;
5. descartam respostas atrasadas e erros pertencentes a consultas antigas.

Esse comportamento é aplicado ao detalhe de caixas anteriores. Ele evita acúmulo de
requisições e impede que um clique antigo sobrescreva a informação do último clique.

A navbar usa a mesma política de substituição. Embora cada destino possua seu próprio
comando, o `ConnectionViewModel` mantém um único cancelamento de navegação compartilhado.
Ao clicar rapidamente em Dashboard, Produtos e Caixa, por exemplo, os carregamentos dos
dois primeiros são cancelados e somente o último módulo permanece ativo.

## Responsividade da interface

- Nenhuma chamada HTTP usa `.Wait()`, `.Result` ou bloqueio síncrono da thread visual.
- Grades de produtos e caixas usam virtualização e reciclagem de linhas.
- Detalhes pesados são carregados sob demanda.
- O estado de carregamento é separado do conteúdo concluído.
- Troca ou encerramento de sessão cancela operações vinculadas e limpa dados anteriores.
- O host possui limite de três segundos para encerramento, evitando espera indefinida.

## Cenários de validação manual

### Inicialização repetida

1. Fechar todas as instâncias do Girofy.
2. Clicar três ou mais vezes rapidamente no atalho ou executável.
3. Confirmar no Gerenciador de Tarefas que existe somente um processo Girofy.
4. Confirmar que a janela permanece responsiva e permite login/navegação.

### Cliques repetidos em ações

1. Clicar rapidamente três vezes em Atualizar nas telas principais.
2. Repetir em busca, paginação e botões de confirmação sem concluir operações destrutivas.
3. Confirmar que não existem chamadas duplicadas, mensagens sobrepostas ou congelamento.

### Troca rápida de caixas

1. Abrir `Caixa > Caixas anteriores`.
2. Selecionar três caixas diferentes em sequência rápida.
3. Confirmar que a interface mantém apenas o último detalhe selecionado.
4. Confirmar que a linha do tempo expande normalmente.
5. Repetir com conexão lenta e confirmar que respostas antigas não reaparecem.

### Uso prolongado

1. Alternar entre Dashboard, Produtos, Caixa, Vendas, Estoque e Relatórios por 15 minutos.
2. Repetir filtros e atualizações.
3. Confirmar ausência de crescimento contínuo de processos, janelas ou tarefas pendentes.
4. Consultar o log local se houver falha inesperada.

## Testes automatizados relacionados

- comandos assíncronos recusam reentrância enquanto estão executando;
- última seleção de caixa vence quando respostas terminam fora de ordem;
- selecionar outro caixa cancela a consulta de detalhe anterior;
- navegar para outro módulo cancela o carregamento iniciado pela navegação anterior;
- troca de sessão limpa o estado do caixa;
- XAML e solução completa são compilados no GitHub Actions para Windows.

## Critério para retomar funcionalidades

Novas funcionalidades devem ser retomadas somente depois que:

- o workflow Windows estiver integralmente verde;
- o artefato self-contained for gerado;
- o teste manual de múltiplas inicializações confirmar uma única instância;
- cliques rápidos nas áreas críticas não bloquearem a interface;
- detalhes de caixa preservarem sempre a última seleção.

## Observabilidade

Falhas não tratadas da interface, processo ou tarefas são registradas no arquivo local do
Girofy. Ao relatar lentidão ou travamento, anexar o horário aproximado, a tela utilizada e
o log correspondente facilita distinguir falha de UI, rede ou backend.
