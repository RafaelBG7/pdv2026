# Acessibilidade nativa no Girofy Windows

Atualizado em 20/08/2026. Este documento descreve apenas o cliente WPF. A Web
mantém sua própria implementação visual; nenhuma preferência desta tela altera
regras financeiras, permissões, estoque ou dados do tenant no backend.

## Funcionalidades disponíveis

Em `Configurações > Acessibilidade`, o usuário pode selecionar:

- texto padrão (100%), médio (110%), grande (120%) ou muito grande (130%);
- texto reforçado, preservando a hierarquia entre corpo, label e título;
- contraste padrão, alto ou muito alto;
- redução de animações e transições decorativas;
- restauração de todos os valores padrão.

O cartão de pré-visualização demonstra texto, preço, borda e botão antes da
gravação. A prévia altera somente recursos visuais da sessão atual. `Salvar`
persiste a configuração; `Restaurar padrões` redefine e persiste os padrões.

## Arquitetura

`IAccessibilityService` define inicialização, prévia, salvamento e restauração.
`AccessibilityService`, na camada Application, normaliza os valores, preserva as
outras preferências do usuário e publica o evento `Changed`.

`WindowsAccessibilityResourceAdapter`, na camada Desktop, observa acessibilidade
e tema. Ele reaplica a paleta Light/Dark e sobrepõe tipografia, peso, bordas,
contraste e duração de animação por recursos WPF dinâmicos. ViewModels e dados da
API não são recarregados quando a aparência muda.

Os tamanhos fixos principais foram migrados para tokens semânticos, de
`FontSizeTiny` até `FontSizeHero`. Pesos usam tokens de corpo, label e destaque.
Essa abordagem evita multiplicar estilos por tela e permite que Dashboard,
Produtos, Categorias, Vendas, Caixa, Estoque, Contas, Relatórios, Auditoria e
Configurações recebam a mesma escala.

## Persistência e segurança

As escolhas ficam no JSON local de preferências, junto do tema e do nome de
usuário lembrado. Elas não são credenciais e, por isso, não usam DPAPI. Tokens de
autenticação continuam armazenados separadamente e protegidos pelo Windows.

Operações de login e troca de tema preservam o bloco de acessibilidade ao atualizar
o arquivo. Valores desconhecidos ou fora do contrato são normalizados, evitando
que uma preferência corrompida impeça a abertura do aplicativo.

## Movimento, tema e sistema operacional

Alto contraste é composto sobre o tema claro ou escuro, sem criar uma terceira
árvore independente de telas. Se o usuário não definiu preferência explícita de
movimento, o App respeita `SystemParameters.ClientAreaAnimation` do Windows. Com
redução ativada, as durações decorativas passam a zero sem remover foco, estado de
carregamento ou feedback funcional.

## Teclado e automação

Inputs, seletores, caixas de marcação e botões permanecem navegáveis por teclado e
com foco visível. Ações críticas de venda, quantidade, remoção/finalização de item
e abertura/fechamento de caixa possuem nomes de automação compreensíveis para
tecnologias assistivas. Mensagens importantes são textuais e não dependem apenas
de cor.

## Testes e publicação

Os testes unitários verificam valores padrão, salvamento e recarga, preservação de
outras preferências, prévia sem persistência, restauração e normalização de entrada
inválida. O workflow Windows #157 concluiu build estrito, testes, publish e geração
do instalador para o commit `375593e`.

Ainda é necessária homologação manual em Windows real para a matriz completa de
DPI, leitor de tela, teclado, Light/Dark, contraste e redução de movimento. Essa
homologação não altera o estado funcional da implementação, mas é requisito de
qualidade para uma distribuição comercial.
