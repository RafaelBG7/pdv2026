# 06 - Fluxo do Sistema

## Fluxo Geral

```mermaid
flowchart TD
    A["Acessar sistema"] --> B["Login ou cadastro"]
    B --> C{"Adega ativa com key?"}
    C -- "Não" --> D["Tela de assinatura"]
    C -- "Sim" --> E["Dashboard"]
    E --> F["Produtos e categorias"]
    E --> G["Caixa"]
    E --> H["Vendas"]
    E --> I["Relatórios"]
    E --> J["Configurações"]
    G --> K["Abrir caixa"]
    K --> L["Nova venda"]
    H --> L
    L --> M["Adicionar produtos"]
    M --> N["Concluir venda / F2"]
    N --> O["Informar pagamentos"]
    O --> P["Finalizar"]
    P --> Q["Baixar estoque"]
    Q --> T["Registrar movimentações e auditoria"]
    P --> R["Detalhe da venda"]
    R --> S["Nova venda por botão, Enter, Espaço ou F3"]
```

## Fluxo de Login

```mermaid
flowchart TD
    A["GET /login"] --> B["Renderiza login.html"]
    B --> C["Usuário envia credenciais"]
    C --> D{"Usuário existe, ativo e senha confere?"}
    D -- "Não" --> E["Flash: usuário ou senha inválidos"]
    E --> B
    D -- "Sim" --> F{"É master do sistema?"}
    F -- "Sim" --> G["Redirect /master/adegas"]
    F -- "Não" --> H{"Adega exige ativação?"}
    H -- "Sim" --> I["Redirect /assinatura"]
    H -- "Não" --> J["Redirect /dashboard"]
```

## Fluxo de Cadastro

```mermaid
flowchart TD
    A["Aba Cadastrar"] --> B["Informa adega, usuário, senha e key opcional"]
    B --> C{"Dados básicos válidos?"}
    C -- "Não" --> X["Erro"]
    C -- "Sim" --> D{"Username único?"}
    D -- "Não" --> X
    D -- "Sim" --> E{"Key informada?"}
    E -- "Sim" --> F{"Key disponível?"}
    F -- "Não" --> X
    F -- "Sim" --> G["Aplica plano e validade"]
    E -- "Não" --> H["Cria sem plano ativo"]
    G --> I["Cria Company e User admin"]
    H --> I
    I --> J["Cria banco MySQL da adega"]
    J --> K["Envia código de verificação por e-mail"]
    K --> L["Usuário confirma código"]
    L --> M{"Adega ativa?"}
    M -- "Não" --> N["Redirect /assinatura"]
    M -- "Sim" --> O["Redirect /dashboard"]
```

## Fluxo de Caixa

```mermaid
flowchart TD
    A["Tela Caixa"] --> B{"Existe caixa aberto?"}
    B -- "Não" --> C["Informar valor inicial"]
    C --> D["POST /caixa/abrir"]
    D --> E["Caixa aberto"]
    B -- "Sim" --> F["Exibe vendas, lucro e valor esperado"]
    F --> T["Resumo por forma de pagamento"]
    F --> U["Linha do tempo expansível"]
    F --> G["Informar valor final"]
    G --> H["POST /caixa/fechar"]
    H --> I{"Valor final == esperado?"}
    I -- "Menor" --> J["Mostra valor faltante"]
    I -- "Maior" --> K["Mostra valor excedido"]
    I -- "Sim" --> L["Fecha caixa"]
```

## Fluxo de Venda

```mermaid
flowchart TD
    A["Nova venda"] --> B{"Caixa aberto?"}
    B -- "Não" --> C["Redireciona para Caixa"]
    B -- "Sim" --> D["Adicionar produtos com autocomplete"]
    D --> E["Total aparece antes do pagamento"]
    E --> F["Concluir venda por botão ou F2"]
    F --> G["Informar formas de pagamento"]
    G --> H{"Itens válidos?"}
    H -- "Não" --> X["Erro e preserva pedido"]
    H -- "Sim" --> I{"Estoque insuficiente bloqueado pela adega?"}
    I -- "Sim" --> X
    I -- "Não" --> J{"Pago >= total final?"}
    J -- "Não" --> X
    J -- "Sim" --> K["Cria venda, itens e pagamentos"]
    K --> L["Baixa estoque via stock_service"]
    L --> P["Cria stock_movements"]
    P --> Q["Registra auditoria da venda"]
    Q --> M["Commit"]
    M --> N["Detalhe da venda"]
    N --> O["Nova venda por botão, Enter, Espaço ou F3"]
```

## Fluxo de Relatório por Produto

```mermaid
flowchart TD
    A["Relatórios"] --> B{"Visualização"}
    B -- "Resumo geral" --> C["Vendas, gráfico, pagamentos e produtos mais vendidos"]
    B -- "Por produto" --> D["Selecionar período, categoria, produto e ordenação"]
    D --> E["Consulta agregada por SaleItem no banco"]
    E --> F["Exibe quantidade, faturamento, custo, lucro, ticket médio e estoque"]
```

## Fluxo de Linha do Tempo do Caixa

```mermaid
flowchart TD
    A["Abre módulo Caixa no Windows"] --> B["Caixa atual selecionado"]
    B --> C["Usuário abre Caixas anteriores"]
    C --> D["Mostra resumo dos 10 caixas recentes"]
    D --> E["Usuário seleciona um caixa"]
    E --> F["GET /api/v1/cash-registers/{id}"]
    F --> G["Mostra resumo e pagamentos autorizados"]
    G --> H["Mostra linha cronológica resumida"]
    H --> I["Usuário expande uma venda"]
    I --> J["Exibe produtos, descontos e pagamentos"]
```

## Fluxo de Importação

```mermaid
flowchart TD
    A["Configurações > Importação"] --> B["Baixar planilha exemplo"]
    B --> C["Preencher categoria, produto, custo e venda"]
    C --> D["Enviar CSV/XLSX"]
    D --> E["Ler linhas"]
    E --> F["Criar categorias ausentes"]
    F --> G["Criar ou atualizar produtos"]
    G --> I["Registrar import/ajuste de estoque"]
    I --> H["Mostrar resumo"]
```

## Fluxo de Entrada/Ajuste de Estoque

```mermaid
flowchart TD
    A["Estoque"] --> B["Entrada ou ajuste"]
    B --> C["Seleciona produto, quantidade e motivo"]
    C --> D["stock_service valida saldo e configuração da adega"]
    D --> E["Atualiza products.stock_quantity"]
    E --> F["Cria stock_movements"]
    F --> G["Cria audit_logs"]
    G --> H["Commit"]
```

## Fluxo de Auditoria

```mermaid
flowchart TD
    A["Ação crítica"] --> B["audit_service sanitiza dados"]
    B --> C["Mascara senhas, tokens e keys"]
    C --> D["Grava usuário, rota, IP e request id"]
    D --> E["Exibe em /auditoria ou /master/auditoria"]
```

## Fluxo do Master

```mermaid
flowchart TD
    A["Login master"] --> B["Painel master"]
    B --> C["Gerenciar adegas"]
    B --> D["Ver logs"]
    B --> E["Limpar logs"]
    B --> F["Acessar adega"]
    B --> G["Configurações > Gerar key"]
    G --> H["Escolher plano e validade"]
    H --> I["Gerar key avulsa ou vinculada"]
```
