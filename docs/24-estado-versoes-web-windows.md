# Estado das Versões Web e Windows

Atualizado em: 10/08/2026

## Objetivo

Este documento separa claramente o estado atual da versão web e da versão Windows nativa
do Girofy. A intenção é facilitar a análise do que já está pronto, do que está parcial e
do que ainda falta antes da entrega para o primeiro cliente.

## Índice

1. Resumo executivo e arquitetura de cada plataforma.
2. Funcionalidades prontas e pendências da WEB.
3. Funcionalidades prontas e pendências do APP WINDOWS.
4. Matriz de paridade e checklist de entrega.
5. Manual funcional separado por módulo.
6. Padrão visual e experiência de uso.
7. Permissões, desempenho e estabilidade.
8. Build, deploy, artifact e diagnóstico.
9. Limites entre plataformas e critérios de conclusão.

## Resumo Executivo

| Frente | Estado | Observação |
|---|---|---|
| Web Flask/Jinja | Em uso controlado | É a versão principal do sistema e roda na OCI em `http://168.75.101.126:18080`. |
| Windows nativo WPF | Prévia funcional | Usa a API da versão web, os mesmos usuários e os mesmos dados. Ainda precisa de validação manual forte no Windows. |
| Banco de dados | Centralizado no servidor | MySQL central + bancos por adega. O cliente Windows não instala nem acessa MySQL. |
| Deploy web | Automatizado | GitHub Actions self-hosted na OCI. |
| Build Windows | Automatizado | GitHub Actions gera artefato de prévia Windows WPF. |
| Atualizador automático | Pausado/cancelado | O ciclo atual foi cortado. A prioridade voltou para funcionalidades e estabilidade. |
| Instalador assinado | Pendente | Sem certificado Code Signing, Windows Smart App Control/SmartScreen pode bloquear o executável. |

## Versão Web

### Estado Atual

A versão web é o produto mais completo do Girofy no momento. Ela roda no servidor OCI e
serve como fonte oficial de dados, autenticação, regras de negócio, permissões e
assinatura.

Acesso atual:

```text
http://168.75.101.126:18080
```

### Arquitetura

- Backend em Python + Flask.
- Frontend em Jinja, HTML, CSS e JavaScript vanilla.
- MySQL como banco principal.
- Banco central para empresas, usuários, assinatura e painel master.
- Banco separado por adega para dados operacionais.
- Docker Compose na OCI.
- Deploy por GitHub Actions self-hosted.
- Cliente Windows consome a API desta mesma aplicação.

### Funcionalidades Web Prontas

Autenticação e usuários:

- Login e logout.
- Cadastro de nova adega.
- Recuperação de senha por e-mail.
- Confirmação de e-mail.
- Lembre de mim na tela de login.
- Usuário master do sistema.
- Usuários por adega.
- Permissões por perfil: funcionário, gerente e admin.
- Bloqueio de usuários inativos.
- Bloqueio de adegas inativas.

Multiadega e painel master:

- Separação de dados por adega.
- Banco MySQL separado por adega.
- Painel master para listar, acessar, editar, inativar e excluir adegas.
- Logs visíveis no painel master.
- Limpeza de logs pelo painel.
- Acesso do master a qualquer adega.

Assinatura e ativação:

- Key de ativação por adega.
- Geração de key no painel master.
- Key com período definido.
- Planos Basic e Pro em tela estética.
- Bloqueio de uso quando a assinatura/key vence.
- Cadastro sem key permitido, mas com operação bloqueada.

Produtos e categorias:

- Cadastro, listagem, edição, ativação, inativação e exclusão de produtos.
- Cadastro, listagem, edição e exclusão de categorias.
- Categoria única por adega, não global.
- Código de barras único por adega.
- Filtro lateral de categorias em produtos.
- Busca de produto por nome ou código.
- Sugestões/autocomplete na busca enquanto digita.
- Ordenação A-Z.
- Produto kit.
- Estoque mínimo.
- Lucro por produto.
- Importação de produtos por CSV/XLSX.
- Exportação CSV para administradores.

Vendas:

- Caixa obrigatório para vender.
- Quando o caixa está fechado, o sistema pergunta se o usuário deseja abrir.
- Nova venda com busca rápida de produto.
- Sugestões enquanto digita, ordenadas alfabeticamente.
- Seleção por mouse e teclado.
- Confirmação de quantidade com padrão 1.
- Venda com múltiplos itens.
- Venda sem estoque quando a configuração da adega permite.
- Estoque pode ficar negativo.
- Desconto em popup.
- F2 para finalizar pedido.
- F3 para nova venda nas telas principais e desconto dentro da venda.
- Múltiplas formas de pagamento.
- Autocomplete do valor faltante por forma de pagamento.
- Troco e valor faltante.
- Histórico de vendas do dia/caixa.
- Detalhe da venda com produtos, pagamentos e lucro.

Caixa:

- Aba Caixa abre no caixa atual por padrão.
- Abertura de caixa.
- Fechamento com validação exata.
- Campo de fechamento em formato monetário `0,00`, aceitando somente números.
- Valor digitado da direita para a esquerda, como nos demais campos monetários.
- Total vendido.
- Ticket médio.
- Lucro do caixa conforme permissão.
- Total por forma de pagamento.
- Linha do tempo de vendas.
- Caixas anteriores em lista resumida e expansível.

Estoque:

- Movimentações de estoque.
- Entrada manual.
- Ajuste manual.
- Registro de origem, usuário, saldo anterior e saldo posterior.
- Baixa automática por venda.
- Baixa de kit pelo produto base.
- Filtros por produto, categoria, tipo, usuário e período.

Relatórios:

- Relatório diário, semanal, mensal, anual e personalizado.
- Gráfico de vendas por período.
- Gráfico diário por horário.
- Horário de pico por quantidade.
- Horário de pico por faturamento.
- Pagamentos por forma.
- Produtos mais vendidos.
- Relatório por produto.
- Filtros por data, categoria, produto e ordenação.

Contas a pagar:

- Cadastro de contas.
- Filtro por abertas, pagas e todas.
- Marcar como paga.
- Reabrir conta.
- Alertas de vencimento.

Configurações:

- Perfil do usuário.
- Senha.
- E-mail.
- Equipe.
- Operação.
- Financeiro.
- Alertas.
- Backup.
- Importação.
- Exportação.
- Suporte.
- Acessibilidade.
- Aparência.

Acessibilidade e UX:

- Tema claro e escuro.
- Menu lateral colapsável.
- Controle de acessibilidade por interruptor.
- Tamanho de texto.
- Contraste de cor.
- Negrito opcional.
- Preferências salvas no navegador.
- Ajustes contínuos de proporção para evitar corte de texto.

Auditoria, logs e backup:

- Auditoria de ações críticas.
- Logs de erro detalhados.
- Mascaramento de dados sensíveis em logs.
- Limpeza automática de auditoria configurada para evitar crescimento excessivo.
- Backup manual.
- Backup por período.

### Pontos Web Ainda Pendentes ou Parciais

- Domínio próprio e HTTPS definitivo.
- CSRF explícito em formulários HTML.
- Rate limit persistente/distribuído para endpoints sensíveis.
- Migrações versionadas com Alembic/Flask-Migrate.
- Restauração guiada de backup pela interface.
- Cobrança real integrada aos planos Basic/Pro.
- Emissão de comprovante/impressão fiscal ou não fiscal.
- Cadastro de clientes.
- Cancelamento/estorno de venda.
- Auditoria mais completa para todas as alterações críticas.
- Otimização específica da tabela "Vendas do período" em relatórios, sem alterar o restante da tela.

## Versão Windows Nativa

### Estado Atual

A versão Windows é um cliente nativo WPF em desenvolvimento. Ela não substitui a versão
web e não derruba a aplicação hospedada. O Windows usa a API da versão web e acessa os
mesmos usuários, adegas, permissões e dados.

### Arquitetura

- C# + .NET 8.
- WPF.
- MVVM.
- Camadas separadas em `Application`, `Infrastructure`, `Desktop` e `UnitTests`.
- Comunicação via API REST do Flask.
- Tokens de sessão.
- Sessão local protegida por DPAPI.
- Logs locais em `%LOCALAPPDATA%\Girofy\logs`.
- Build `win-x64` autocontido via GitHub Actions.

### Funcionalidades Windows Prontas

Base do aplicativo:

- Tela de login nativa.
- Lembrar usuário.
- Mostrar senha.
- Abertura da versão web pelo botão.
- Shell autenticado.
- Navbar lateral.
- Logout.
- Persistência segura de sessão com DPAPI.
- Logs locais.

Dashboard:

- Resumo operacional da adega.
- Indicadores principais.
- Dados respeitando permissões.

Produtos:

- Listagem de produtos.
- Busca e filtros.
- Cadastro de produto.
- Edição básica.
- Integração com categorias.
- Ajustes de UX em andamento para aproximar da versão web.

Categorias:

- Listagem.
- Cadastro.
- Edição.
- Exclusão quando permitido.

Vendas:

- Tela de vendas nativa.
- Nova venda em popup.
- Pesquisa de produto.
- Sugestões de produto.
- Navegação por teclado em evolução.
- Confirmação de quantidade.
- Carrinho de venda.
- Remoção de item.
- Desconto em popup.
- Pagamento em tela separada.
- Formas: dinheiro, Pix, débito e crédito.
- Autocomplete de valor faltante em pagamento.
- F2 para finalizar.
- F3 para nova venda/desconto conforme contexto.
- Enter e Espaço para iniciar nova venda depois de venda concluída.
- Esc para fechar a tela de nova venda.

Caixa:

- Consulta de caixa atual.
- Abertura de caixa.
- Fechamento de caixa.
- Resumo de vendas do caixa.
- Totais por forma de pagamento.

Estoque:

- Movimentações.
- Entrada manual.
- Ajuste manual.
- Histórico com filtros.

Relatórios:

- Resumo por período.
- Relatório por produto.
- Pagamentos.
- Produtos mais vendidos.

Contas a pagar:

- Listagem.
- Cadastro.
- Marcar como paga.
- Reabrir.

Auditoria:

- Listagem.
- Filtros.
- Detalhes expansíveis.

Configurações:

- Perfil.
- Senha.
- Regras operacionais.
- Taxas de pagamento.
- Backup.
- Importação.
- Exportação.
- Gestão básica de equipe.
- Ativação por key.

### Pontos Windows Ainda Pendentes ou Parciais

- Validação manual completa em Windows 10 e Windows 11.
- Assinatura digital do executável/instalador.
- Instalador oficial com experiência final para cliente.
- Definição do canal de distribuição.
- Autoatualizador pausado/cancelado no momento.
- HTTPS/domínio para remover exceções de HTTP.
- Finalizar paridade de UX com a versão web em produtos, configurações e vendas.
- Ajustar estados de seleção que ainda ficam brancos em algumas tabelas.
- Melhorar navegação por setas em sugestões de produto.
- Padronizar todos os campos monetários em formato `0,00`.
- Completar testes manuais de venda, caixa, estoque, relatórios e configurações.
- Medir desempenho em máquinas fracas do cliente.
- Reduzir peso visual e custo de renderização onde necessário.

## Matriz de Paridade

| Módulo | Web | Windows | Falta para paridade inicial |
|---|---|---|---|
| Login | Pronto | Pronto | Assinatura digital do app para evitar bloqueio do Windows. |
| Usuários e permissões | Pronto | Parcial | Garantir que todas as telas Windows escondam ou bloqueiem ações conforme permissão. |
| Multiadega | Pronto | Pronto via API | Validar manualmente troca de usuário/adega no Windows. |
| Painel master | Pronto | Parcial/pendente | Windows ainda não deve ser prioridade para master completo. |
| Assinatura/key | Pronto | Parcial | Validar ativação e bloqueios em todos os fluxos nativos. |
| Produtos | Pronto | Pronto no recorte atual | Validar cadastro, expansão, filtros e permissões em Windows real. |
| Categorias | Pronto | Pronto no recorte atual | Validar bloqueio de exclusão e mensagens retornadas pela API. |
| Vendas | Pronto | Pronto no recorte atual | Continuar testes de estresse, teclado, máscaras e cliques repetidos. |
| Caixa | Pronto | Pronto no recorte atual | Validar abertura, fechamento, expansão e totais em cenário real. |
| Estoque | Pronto | Pronto no recorte atual | Validar histórico, entrada, ajuste e baixa por venda em massa. |
| Relatórios | Pronto | Pronto no recorte atual | Validar desempenho e consistência dos agregados com alto volume. |
| Contas a pagar | Pronto | Parcial | Validar cadastro, pagamento e reabertura em produção controlada. |
| Notificações e e-mail | Pronto | Pronto no recorte atual | APP consome notificações; envio de e-mail permanece no backend WEB. |
| Auditoria | Pronto | Pronto no recorte atual | Validar paginação e expansão com histórico extenso. |
| Configurações | Pronto | Parcial | Reorganizar UX por abas e validar todas as ações. |
| Backup | Pronto | Parcial | Windows chama API, mas restore guiado ainda falta. |
| Importação/exportação | Pronto | Parcial | Validar arquivos reais e erros de planilha no Windows. |
| Acessibilidade | Pronto | Pendente/parcial | Levar controles equivalentes para o app nativo se necessário. |
| Deploy web | Pronto | Não se aplica | Manter pipeline OCI estável. |
| Build Windows | Não se aplica | Pronto para prévia | Criar instalador assinado antes da entrega comercial. |
| Atualização automática | Não se aplica | Pausado | Retomar apenas após estabilizar funcionalidades. |

## Checklist Para o Primeiro Cliente Windows

Antes de entregar para o primeiro cliente usando Windows nativo:

1. Confirmar que a versão web está funcionando como retaguarda e fonte de verdade.
2. Gerar novo artefato Windows pelo GitHub Actions.
3. Testar login com usuário real da adega do cliente.
4. Abrir caixa.
5. Cadastrar ou revisar produtos e categorias.
6. Realizar venda com um item.
7. Realizar venda com múltiplos itens.
8. Realizar venda com desconto.
9. Realizar venda com múltiplas formas de pagamento.
10. Conferir baixa de estoque.
11. Fechar caixa com valor correto.
12. Conferir relatório do dia.
13. Conferir histórico de vendas.
14. Conferir logs locais se houver erro.
15. Fazer backup antes e depois da operação inicial.

## Leitura do Estado Atual

Para decisão prática:

- A versão web está mais pronta para operação.
- A versão Windows já tem base suficiente para testes manuais reais.
- O maior risco da versão Windows hoje não é regra de negócio, e sim distribuição,
  assinatura digital, acabamento de UX e validação manual em máquina do cliente.
- O atualizador automático foi pausado para evitar abrir outro ciclo de complexidade
  antes da versão inicial ficar estável.

---

## Como Ler Esta Documentação

Este manual usa os seguintes nomes de forma rigorosa:

- **WEB**: interface aberta no navegador, renderizada pelo Flask com Jinja, HTML, CSS e
  JavaScript. É também onde o backend, a API e as regras oficiais são executados.
- **APP WINDOWS**: aplicativo nativo WPF, escrito em C#/.NET. Ele apresenta uma interface
  própria, mas consulta e altera dados por meio da API hospedada no servidor WEB.
- **COMPARTILHADO**: regra ou dado mantido no servidor e utilizado pelas duas interfaces.
- **NÃO SE APLICA**: recurso específico de uma plataforma, sem equivalente necessário na outra.

Uma função existir na WEB não significa automaticamente que sua tela exista no APP WINDOWS.
Da mesma forma, uma melhoria visual do APP não modifica os templates da WEB. Quando as duas
interfaces executam a mesma operação, a validação definitiva continua no backend.

## Visão de Funcionamento das Duas Plataformas

| Responsabilidade | WEB | APP WINDOWS |
|---|---|---|
| Interface | Navegador, templates Jinja e JavaScript | Executável WPF nativo |
| Regra de negócio | Executada no backend Flask | Solicita a operação à API; não replica a regra crítica |
| Dados | Lê e grava no MySQL do servidor | Não usa banco local; lê e grava pela API |
| Autenticação | Sessão Flask/cookie | Access token e refresh token |
| Sessão persistente | Cookie conforme opção de login | Refresh token protegido pelo DPAPI do Windows |
| Preferências visuais | `localStorage` do navegador | JSON em `%LOCALAPPDATA%\Girofy` |
| Logs da interface | Navegador e logs do servidor | Arquivos em `%LOCALAPPDATA%\Girofy\logs` |
| Atualização | Novo deploy passa a valer ao recarregar a página | Novo artifact precisa ser baixado e substituído manualmente |
| Fonte de verdade | Backend Flask + MySQL | Backend Flask + MySQL, acessados pela API |

## Manual Funcional por Módulo

### 1. Autenticação, cadastro e recuperação de senha

#### WEB

- A tela pública possui as abas `Entrar` e `Cadastrar`.
- O login aceita usuário e senha, valida usuário ativo, adega ativa e estado da assinatura.
- `Lembre de mim` controla a persistência da sessão no navegador.
- O cadastro cria a adega, o primeiro administrador e o banco operacional da empresa.
- A key pode ser informada no cadastro. Cadastro sem key continua possível, mas a operação
  autenticada fica bloqueada até a ativação.
- A recuperação de senha recebe o e-mail, gera token temporário e envia o link de redefinição.
- Confirmação de e-mail e troca de e-mail usam códigos ou links enviados pelo backend.
- Tentativas inválidas de login são limitadas temporariamente.

#### APP WINDOWS

- O login é uma tela WPF nativa e utiliza o mesmo usuário cadastrado na WEB.
- `Lembrar usuário` guarda somente a identificação necessária para facilitar o próximo acesso.
- `Mostrar senha` alterna a visualização sem mudar o valor digitado.
- O token renovável é armazenado de forma protegida com DPAPI; senha não é salva em texto puro.
- Quando a assinatura exige ativação, o formulário muda para o fluxo de key.
- `Criar conta` abre o cadastro público da WEB no navegador, evitando duplicar no APP um fluxo
  administrativo e de e-mail que já é oficial no servidor.
- `Esqueci minha senha` abre um popover nativo, solicita o envio pelo serviço WEB e informa o
  resultado sem revelar se determinado e-mail pertence a uma conta.
- Se a sessão expirar, o APP limpa o contexto autenticado e volta ao login.

### 2. Dashboard

#### WEB

- Mostra vendas, faturamento, lucro autorizado, situação do caixa, estoque baixo e contas.
- Oferece atalhos para venda, produtos, caixa e relatórios.
- O botão de venda também responde ao atalho global `F3` quando o foco não está em um campo.
- Os cards e avisos são calculados pelo backend para a adega autenticada.

#### APP WINDOWS

- Consulta um snapshot resumido da mesma adega e respeita as permissões do usuário.
- Mostra cards operacionais, estados de carregamento, erro recuperável e botão de atualização.
- A navegação ocorre dentro do shell nativo; não abre uma nova página a cada módulo.
- A atualização é assíncrona para não bloquear a janela enquanto a API responde.

### 3. Produtos e categorias

#### WEB

- Produtos podem ser buscados por nome ou código de barras, filtrados por categoria, status,
  estoque e preço, e ordenados conforme as opções da tela.
- O autocomplete sugere produtos e categorias enquanto o usuário digita.
- A linha do produto é clicável e expansível, mostrando informações financeiras e de estoque.
- O cadastro e a edição incluem nome, código, categoria, custo, preço, estoque, estoque mínimo,
  status e configuração de kit.
- Alterações que afetam saldo exigem motivo para formar um histórico auditável.
- Importação aceita CSV/XLSX; exportação CSV depende de permissão administrativa.
- Categorias são exclusivas da adega. A exclusão é bloqueada quando existem produtos associados.

#### APP WINDOWS

- A aba `Produtos` possui busca, filtro de status, ordenação e paginação consultadas na API.
- Busca e filtros usam o componente escuro padronizado; o menu aberto mantém fundo escuro,
  texto claro e estados de foco/seleção visíveis.
- O produto é clicável. Selecionar uma linha expande os detalhes no próprio contexto da tabela;
  selecionar novamente ou outro item controla qual detalhe permanece aberto.
- O detalhe mostra status, código, categoria, tipo, estoque atual/mínimo, custo, preço e lucro,
  omitindo valores que a permissão não autoriza.
- Cadastro e edição são realizados em painel nativo e enviados à API.
- A aba `Categorias` permite listar, cadastrar, editar e excluir quando a regra permitir.
- As tabelas usam paginação e virtualização para evitar renderizar todos os itens de uma vez.

### 4. Vendas

#### WEB

- Uma venda só pode ser concluída com caixa aberto.
- Produtos são pesquisados por nome/código, adicionados com quantidade e validados no servidor.
- O carrinho calcula subtotal, desconto, total, valor pago, valor restante e troco.
- Aceita dinheiro, Pix, débito e crédito, inclusive combinação de formas.
- `F2` avança para pagamento; `F3` abre desconto dentro da venda.
- A configuração da adega decide se estoque insuficiente bloqueia ou permite saldo negativo.
- Ao finalizar, são gravados venda, itens, pagamentos, baixa de estoque e vínculo com o caixa.
- O histórico lista as vendas e o detalhe apresenta itens, pagamentos, totais e lucro autorizado.

#### APP WINDOWS

- A tela mantém histórico e criação de venda em experiência nativa.
- A pesquisa usa carregamento controlado, cancelamento de respostas antigas e limites de resultado
  para impedir travamento durante digitação rápida ou cliques repetidos.
- A nova venda abre em painel/modal, aceita carrinho, quantidade, remoção e desconto.
- O pagamento aceita dinheiro, Pix, débito e crédito e sugere o valor restante.
- `F2`, `F3`, `Enter`, `Espaço` e `Esc` são tratados conforme o contexto; atalhos não devem criar
  comandos duplicados quando o usuário clica repetidamente.
- Depois da confirmação, o APP atualiza o histórico usando os dados retornados pelo servidor.
- O detalhe da venda usa os dados oficiais da API; nenhuma baixa de estoque é calculada localmente.

### 5. Caixa

#### WEB

- `Caixa atual` mostra abertura, saldo inicial, total vendido, saldo esperado, lucro autorizado,
  formas de pagamento e linha do tempo de vendas.
- Abertura cria um caixa para o usuário/adega quando não existe outro aberto.
- Fechamento exige o valor final e o backend valida a conferência.
- `Caixas anteriores` lista caixas fechados e expande o histórico completo escolhido.
- Cada venda da linha do tempo também pode ser expandida para mostrar itens e pagamentos.

#### APP WINDOWS

- A navbar interna separa `Caixa atual` e `Caixas anteriores`.
- A tela atual organiza resumo, formas de pagamento e movimentações em cards do padrão Girofy.
- Caixas anteriores são carregados como lista resumida e virtualizada.
- Um clique carrega e expande o caixa. Um novo clique no mesmo caixa minimiza as informações.
- O detalhe contém quanto foi vendido, saldo inicial/final, totais por pagamento e linha do tempo.
- As vendas da linha do tempo são expansíveis.
- O detalhe é solicitado sob demanda: o APP não baixa antecipadamente todo o histórico.
- O scroll utiliza rolagem física/suave onde necessário e virtualização na listagem para reduzir
  input lag em máquinas mais fracas.

### 6. Estoque

#### WEB

- Exibe histórico de movimentações com produto, tipo, quantidade, origem, usuário, saldo anterior,
  saldo posterior, motivo e data.
- Permite filtros por produto, categoria, tipo, origem, usuário e período.
- Entrada manual soma quantidade ao saldo e registra custo/motivo quando informado.
- Ajuste manual define ou corrige saldo e exige justificativa.
- Vendas geram baixa automática; kits baixam o produto base conforme a composição.

#### APP WINDOWS

- A navbar interna separa `Movimentações` e `Entradas e ajustes`.
- A tela de movimentações possui busca, categoria, tipo, origem e ações de filtrar/limpar.
- Pesquisa e seletores seguem o mesmo tema escuro usado em Produtos.
- A tabela apresenta dados operacionais com virtualização e reaproveitamento de linhas.
- Entrada manual pesquisa o produto, define quantidade, custo, motivo e observação.
- Ajuste manual seleciona produto, modo de ajuste, quantidade/saldo desejado e motivo.
- Todos os comandos são enviados à API; após sucesso, o histórico é recarregado.

### 7. Contas a pagar

#### WEB

- Permite cadastrar descrição, valor e vencimento.
- Filtra contas abertas, pagas ou todas.
- Permite marcar como paga e reabrir, respeitando permissão.
- Contas próximas ou vencidas alimentam os alertas do sistema.

#### APP WINDOWS

- Lista contas e seus estados em interface nativa.
- Permite cadastro, pagamento, reabertura, filtros e atualização.
- Mensagens de erro/sucesso permanecem na própria tela e não encerram o aplicativo.
- Datas, valores e transições continuam validados pelo backend.

### 8. Relatórios

#### WEB

- A navbar interna separa `Resumo geral` e `Por produto`.
- Períodos disponíveis: diário, semanal, mensal, anual e personalizado.
- O resumo mostra número de vendas, faturamento, lucro, ticket médio, itens e descontos.
- Mostra horário de pico, melhor hora por quantidade e por faturamento.
- O gráfico por horário alterna entre faturamento e quantidade.
- A parte inferior reúne vendas do período, formas de pagamento e produtos mais vendidos.
- O relatório por produto aceita busca, categoria/ordenação quando disponíveis e apresenta
  quantidade, receita, custo, lucro, ticket e estoque.

#### APP WINDOWS

- A tela foi organizada nas abas nativas `Resumo geral` e `Por produto`, sem exibir os dois
  relatórios simultaneamente.
- O período, a métrica e as datas são enviados à API pelos filtros.
- Os cards mostram vendas, itens, faturamento, subtotal, lucro, descontos e ticket médio.
- O gráfico usa buckets retornados pelo servidor e destaca valor/quantidade conforme a métrica.
- Pagamentos e produtos mais vendidos são apresentados em cards laterais.
- O relatório por produto possui busca, ordenação, indicadores, tabela e paginação.
- A tabela é virtualizada para manter a janela responsiva.
- A estilização segue a WEB sem copiar literalmente o HTML: mesmas cores, hierarquia, estados e
  significado visual, usando componentes WPF nativos.

### 9. Notificações e e-mail

#### WEB

- O sino abre um popover pequeno ancorado ao topo, não uma página inteira.
- Alertas incluem estoque baixo, produto sem estoque, contas próximas do vencimento e vencidas.
- É possível filtrar, marcar uma como lida, dispensar e marcar todas como lidas.
- O contador mostra pendências não lidas e o estado crítico recebe destaque visual.
- E-mails operacionais são produzidos no servidor conforme preferências, destinatários e regras
  de deduplicação; o APP não envia SMTP diretamente.

#### APP WINDOWS

- O sino abre um popover compacto inspirado na WEB.
- Um clique abre; outro clique no sino fecha. Não é necessário clicar e segurar.
- Clicar fora também pode encerrar o popover conforme o comportamento do shell.
- O painel apresenta contador, severidade, título, descrição, data e ações permitidas.
- Atualização, leitura e dispensa chamam a API de notificações.
- A consulta é protegida contra exceções não tratadas: falha de rede deve mostrar erro seguro,
  sem impedir a abertura do aplicativo.
- Notificações por e-mail são responsabilidade do backend WEB; o APP apenas altera preferências
  quando a tela oferece essa configuração.

### 10. Auditoria

#### WEB

- Registra ações críticas com usuário, módulo, entidade, descrição, data e valores sanitizados.
- A tela possui filtros, paginação e linhas expansíveis.
- O master pode consultar eventos globais conforme autorização.

#### APP WINDOWS

- Consulta logs autorizados pela API.
- Possui busca, filtros, paginação, atualização e limpeza de filtros.
- Detalhes são expansíveis e valores sensíveis continuam mascarados pelo servidor.
- É uma consulta somente leitura; não altera o evento auditado.

### 11. Configurações, equipe e operação

#### WEB

- Reúne perfil, credenciais, equipe, permissões, operação, financeiro, alertas, aparência,
  acessibilidade, backup, importação, exportação e suporte.
- Administradores gerenciam usuários e permissões conforme o plano/regra vigente.
- Regras como permitir estoque negativo e taxas de pagamento afetam os cálculos do backend.
- Backup e exportação são gerados no servidor.

#### APP WINDOWS

- Oferece telas nativas para perfil, senha, operação, taxas, alertas, backup, importação,
  exportação, equipe básica e ativação.
- A disponibilidade de cada ação é derivada das permissões retornadas na sessão.
- Seleção de arquivo usa o diálogo nativo do Windows.
- Download/exportação usa o seletor nativo para definir o destino.
- Configurações administrativas ainda não expostas no APP continuam disponíveis na WEB.

## Padrão Visual e Experiência de Uso

### Estilo da WEB

- Tokens CSS são definidos em `app/static/css/style.css` para tema claro e escuro.
- Roxo identifica marca, seleção e ações principais; ciano reforça foco e detalhes ativos.
- Verde representa sucesso; âmbar, atenção; vermelho, erro/perigo; azul, informação.
- Sidebar escura, item ativo com superfície destacada e borda/acento ciano.
- Cards usam superfície elevada, borda discreta, cantos arredondados e espaçamento consistente.
- Campos mantêm contraste entre fundo, borda, texto, placeholder, foco e estado desabilitado.
- Tabelas utilizam cabeçalho destacado, linhas legíveis, estados vazios e expansão contextual.
- Layout responde a telas menores reorganizando colunas, filtros e navegação.
- Acessibilidade permite escala de texto, contraste e negrito, persistidos no navegador.

### Estilo do APP WINDOWS

- Tokens WPF ficam em `desktop_wpf/src/Girofy.Desktop/Themes/Colors.xaml`.
- O APP utiliza fundo azul-marinho profundo, superfícies elevadas e a mesma semântica de roxo,
  ciano, verde, âmbar, vermelho e azul da WEB.
- `TextBox`, `PasswordBox` e `ComboBox` possuem templates nativos escuros. O dropdown não herda
  o fundo branco padrão do Windows.
- Estados de hover, foco, seleção, clique, carregamento e desabilitado precisam permanecer visíveis.
- Cards usam bordas discretas, cantos arredondados e hierarquia entre título, rótulo e valor.
- Navbars internas são usadas quando um módulo possui contextos diferentes, como Caixa, Estoque
  e Relatórios.
- Popovers, como Notificações, são compactos e ancorados à ação que os abriu.
- Tabelas extensas usam virtualização, paginação e carregamento sob demanda.
- A WEB é referência de linguagem visual; o APP preserva comportamentos nativos de teclado,
  foco, scroll e janela em vez de simular um navegador.

## Permissões e Exposição de Dados

### WEB

- Rotas protegidas validam autenticação, adega e permissão no servidor.
- A interface pode ocultar botões, mas o bloqueio real acontece na rota/serviço.
- Lucro, custo, relatórios, caixa, auditoria, usuários e exportações podem exigir permissões próprias.

### APP WINDOWS

- O APP recebe as permissões da sessão e oculta/desabilita módulos e comandos incompatíveis.
- Toda requisição protegida envia o token; a API repete a validação no servidor.
- Ocultar um campo no XAML não é considerado controle de segurança isolado.
- Quando custo ou lucro não são autorizados, o APP mostra valor indisponível ou omite o bloco.

## Desempenho e Estabilidade

### WEB

- Paginação e filtros reduzem o volume retornado nas listagens.
- Autocomplete limita sugestões e evita carregar o catálogo completo no DOM.
- Operações longas devem produzir feedback visual e mensagens seguras.
- Consultas agregadas de relatório precisam ser medidas à medida que o histórico cresce.

### APP WINDOWS

- Chamadas HTTP são assíncronas e não devem bloquear a thread de interface.
- Comandos assíncronos impedem execução duplicada enquanto uma operação está em andamento.
- Respostas antigas de pesquisas rápidas devem ser ignoradas/canceladas.
- DataGrid e listas extensas utilizam virtualização e modo de reciclagem.
- Detalhes de caixa e venda são carregados somente quando solicitados.
- Scroll não deve conter manipuladores pesados por evento nem controles aninhados ilimitados.
- Exceções globais são registradas localmente; erros recuperáveis devem ficar na tela.

## Build, Deploy e Artifact

### WEB

- Código principal é publicado pelo workflow de deploy OCI.
- O deploy usa Docker Compose e runner self-hosted conforme a configuração vigente.
- Alterações na WEB só chegam ao servidor depois do workflow de deploy correspondente.
- Banco, segredos e arquivos persistentes não devem ser empacotados como código-fonte.

### APP WINDOWS

- O workflow `Build Windows WPF preview` compila e publica `win-x64` autocontido.
- Pode ser iniciado por `pull_request`, por push elegível na `main` ou manualmente com
  `workflow_dispatch`.
- O resultado é enviado como artifact do GitHub Actions.
- Artifacts antigos consomem a cota da organização/repositório. Se a cota for atingida, é preciso
  excluir artifacts antigos e aguardar a atualização do uso, normalmente entre 6 e 12 horas.
- O aviso de `punycode`/Node emitido pelo `upload-artifact` é uma advertência da action e não é a
  causa de falha quando o erro informado é `Artifact storage quota has been hit`.
- O artifact atual é uma prévia portátil; assinatura digital e instalador comercial continuam
  pendentes.

## Diagnóstico de Problemas

### WEB

1. Confirmar o endpoint `/health` e o estado dos containers.
2. Conferir logs da aplicação e do proxy/deploy.
3. Validar conexão com banco central e banco da adega.
4. Reproduzir com o mesmo usuário e permissões.
5. Preservar dados sensíveis ao copiar logs.

### APP WINDOWS

1. Confirmar que o servidor configurado responde.
2. Conferir `%LOCALAPPDATA%\Girofy\logs`.
3. Identificar timestamp, nível, exceção interna e operação HTTP anterior.
4. Validar se a falha ocorre antes do login, ao montar o shell ou ao abrir um módulo.
5. Em travamento visual, testar cliques rápidos, scroll, pesquisa e abertura repetida de detalhes.
6. Não apagar preferências/sessão antes de guardar uma cópia dos logs necessários ao diagnóstico.

## Funções que Não Devem Ser Confundidas

| Função | WEB | APP WINDOWS |
|---|---|---|
| Hospedar API | Sim | Não |
| Acessar MySQL diretamente | Sim, pelo backend | Não |
| Enviar e-mail por SMTP | Sim, pelo backend | Não |
| Gerar artifact Windows | Não | Sim, pelo GitHub Actions |
| Atualizar automaticamente após deploy | Sim, ao recarregar | Não; requer novo binário |
| Painel master completo | Sim | Não é prioridade atual |
| Tema claro/escuro completo | Sim | Tema escuro padronizado atual |
| Trabalhar totalmente offline | Não | Não |
| Fonte oficial das regras | Backend WEB | Não; consome o backend |

## Critério para Considerar uma Função Concluída

### WEB

Uma função WEB está concluída quando a rota, validação, persistência, permissão, template,
mensagem de erro e teste aplicável funcionam no ambiente hospedado.

### APP WINDOWS

Uma função do APP está concluída quando a API necessária existe, a tela nativa cobre o fluxo,
permissões e erros são tratados, a interface permanece responsiva, o build Windows passa e o
fluxo é validado manualmente em Windows 10/11. Ter apenas o XAML ou apenas o endpoint não significa
que a função inteira esteja concluída.
