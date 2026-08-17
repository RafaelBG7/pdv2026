# Versão atual — 13/08/2026

> Documento histórico. O estado oficial mais recente está em [31-estado-atual-17-08-2026.md](31-estado-atual-17-08-2026.md).

Este é o documento oficial de continuidade do Girofy a partir do commit de marco de 13/08/2026. Ele separa o que pertence ao produto Web/API do que pertence ao aplicativo Windows e registra infraestrutura, segurança, banco, testes, deploy e pendências conhecidas.

## 1. Regra de separação entre plataformas

| Componente | Web/API | Aplicativo Windows |
|---|---|---|
| Interface | Flask/Jinja, HTML, CSS e JavaScript | WPF nativo em .NET 8/XAML |
| Regras de negócio | Fonte oficial no backend Flask | ViewModels apresentam dados e chamam a API |
| Autenticação | Sessão web e tokens REST | Access/refresh token pela API |
| Dados | MySQL central + banco por tenant | Não possui banco local e não acessa MySQL |
| Deploy | Docker Compose na OCI | ZIP self-contained win-x64 no GitHub Actions |
| Schema | Alembic central e tenant | Não executa migrations |
| Atualização | Workflow Deploy OCI Self Hosted | Workflow Build Windows WPF preview |

Uma funcionalidade só é considerada disponível no Windows quando existe endpoint compatível, implementação no cliente e validação do build. A existência na Web não significa automaticamente paridade no aplicativo.

## 2. Web/API — estado atual

### Base funcional

- cadastro de adega, confirmação de e-mail, login, logout e recuperação de senha;
- painel master, empresas, usuários, perfis e permissões;
- assinatura por key, planos apresentados e bloqueio por expiração;
- produtos, categorias, kits, estoque mínimo, busca, filtros, importação e exportação;
- estoque com entrada, ajuste, baixa por venda, estorno e histórico antes/depois;
- vendas com múltiplos itens, desconto, pagamentos mistos, troco e lucro;
- cancelamento/estorno lógico de venda, motivo, autorização, auditoria e devolução de estoque;
- caixa atual, abertura, fechamento, formas de pagamento, saldo antes das vendas e histórico de caixas;
- relatórios gerais e por produto, horários, pagamentos e produtos mais vendidos;
- contas a pagar, notificações no painel e alertas por e-mail;
- configurações operacionais, financeiras, aparência, acessibilidade e backup;
- auditoria e logs com `request_id` e mascaramento de segredos.

### Backend e API

- API REST v1 consumida pelo WPF;
- tokens de acesso e renovação com revogação/rotação;
- respostas e permissões alinhadas ao tenant autenticado;
- serviços compartilhados para vendas, caixa, estoque, dashboard e catálogo;
- health checks Web e API verificam MySQL e Redis;
- erros 429 e indisponibilidade do rate limiter possuem resposta controlada.

### Banco e multi-tenant

- banco central para empresas, usuários, autenticação e administração;
- banco operacional separado para cada adega;
- árvores `migrations/central` e `migrations/tenant` independentes;
- revisions atuais `central_0002` e `tenant_0002`;
- bancos existentes adotados por baseline validado, sem recriar dados;
- novas adegas recebem database, migrations completas e sincronização inicial;
- produção usa `SCHEMA_MANAGEMENT_MODE=verify` e falha se o schema estiver atrasado;
- deploy gera backup completo antes de executar migrations.

### Segurança e infraestrutura

- CSRF em operações Web mutáveis;
- política de senha e confirmação de e-mail;
- rate limit distribuído por Redis em login, cadastro, recuperação, API e ações sensíveis;
- proxy confiável configurado para Caddy;
- MySQL e Redis não são publicados diretamente na internet;
- Docker Compose executa app, MySQL, Redis, backup e Caddy;
- GitHub Actions serializa deploys para impedir migrations concorrentes.

### Publicação Web

- ambiente atual: OCI em `http://168.75.101.126:18080`;
- pipeline: testes → build → backup → migrations central/tenants → containers → health checks;
- falha em backup, migration, Redis ou health check interrompe o deploy;
- domínio próprio e HTTPS definitivo continuam pendentes.

## 3. Aplicativo Windows WPF — estado atual

### Arquitetura

- solução em `desktop_wpf/Girofy.Desktop.sln`;
- projetos Desktop, Application, Infrastructure e testes unitários;
- cliente HTTP centralizado em `GirofyApiClient`;
- armazenamento protegido da sessão/tokens no Windows;
- executável self-contained `win-x64`, sem Python ou MySQL local.

### Funcionalidades disponíveis

- login, criação de conta, confirmação e recuperação de senha via API;
- dashboard e notificações em popover compacto por clique;
- produtos pesquisáveis e detalhe expansível;
- categorias e estoque com filtros e padrão visual do sistema;
- vendas, detalhe expansível e cancelamento autorizado;
- caixa atual e caixas anteriores em navegação própria;
- detalhe expansível de caixas, formas de pagamento e linha do tempo;
- clique repetido minimiza o caixa já expandido;
- saldo existente antes de cada venda no histórico do caixa;
- relatórios com identidade visual alinhada à versão Web;
- permissões refletidas na interface e confirmadas pelo servidor.

### Estabilidade e desempenho

- trava de instância única;
- comandos assíncronos protegidos contra reentrada;
- cancelamento de pesquisas e carregamentos substituídos;
- descarte de respostas antigas/fora de ordem;
- carregamento sob demanda de detalhes e linhas do tempo;
- melhorias de scroll e redução de trabalho desnecessário na UI;
- erros globais registrados sem encerrar silenciosamente o aplicativo.

### Distribuição

- workflow `Build Windows WPF preview` executa contratos Python, restore, testes .NET e publish;
- artifact ZIP contém a aplicação self-contained;
- retenção padrão reduzida para 7 dias para controlar a cota do GitHub;
- somente o artifact mais recente deve ser mantido durante desenvolvimento;
- instalador assinado e atualizador automático continuam fora do marco atual.

## 4. Padrão visual compartilhado

As duas interfaces usam fundo escuro, superfícies em azul-noturno, bordas discretas, roxo como ação principal, ciano como destaque e cores semânticas para sucesso, alerta e erro. Cards, filtros, tabs, campos, estados vazios e detalhes expansíveis devem seguir a mesma hierarquia, mas respeitando os componentes nativos de cada plataforma.

- **Web:** tokens e componentes em `app/static/css/style.css`, templates Jinja e interações em `app/static/js/main.js`.
- **Windows:** resources/dicionários XAML, controles WPF e ViewModels; não copiar HTML/CSS para o app.

## 5. Testes e critério de continuidade

Antes de cada entrega:

```bash
.venv/bin/python -m unittest discover
dotnet test desktop_wpf/Girofy.Desktop.sln --configuration Release
```

CI também valida carregamento das duas árvores Alembic, sintaxe dos scripts de deploy e bindings WPF. Testes manuais no Windows continuam obrigatórios para scroll, múltiplos cliques, expansão de linhas e janelas em diferentes resoluções.

## 6. Workflows e artifacts

- `Deploy OCI Self Hosted`: publica somente Web/API/infraestrutura;
- `Build Windows WPF preview`: gera somente o aplicativo Windows;
- alterações apenas em documentação não precisam publicar a OCI;
- alterações de contrato da API podem disparar os dois pipelines;
- artifacts antigos devem ser excluídos regularmente; em 13/08/2026 a limpeza deixou apenas o ZIP Windows mais recente e seis execuções recentes bem-sucedidas;
- a cota do GitHub pode levar de 6 a 12 horas para refletir exclusões.

## 7. Pendências priorizadas

### Web/API

1. domínio e HTTPS definitivo;
2. restauração guiada de backup;
3. cobrança real e regras comerciais dos planos;
4. impressão/comprovante;
5. cadastro de clientes;
6. cancelamento parcial por item e integração com adquirentes;
7. ampliar observabilidade e auditoria de operações críticas.

### Windows

1. ciclo completo de homologação manual em Windows real;
2. instalador e assinatura Code Signing;
3. atualização automática quando a estratégia for retomada;
4. validação de impressão e periféricos quando implementados no backend;
5. continuar paridade módulo a módulo sem duplicar regras de negócio.

## 8. Documentos de referência

- arquitetura geral: [03-arquitetura.md](03-arquitetura.md);
- banco: [04-modelagem-banco.md](04-modelagem-banco.md);
- API: [09-api.md](09-api.md);
- deploy: [12-deploy.md](12-deploy.md);
- segurança: [14-seguranca.md](14-seguranca.md);
- testes: [15-testes.md](15-testes.md);
- Web versus Windows: [24-estado-versoes-web-windows.md](24-estado-versoes-web-windows.md);
- caixa Windows: [25-caixas-windows.md](25-caixas-windows.md);
- notificações: [25-notificacoes-web-windows-email.md](25-notificacoes-web-windows-email.md);
- estabilidade Windows: [26-desempenho-estabilidade-windows.md](26-desempenho-estabilidade-windows.md);
- cancelamento: [27-cancelamento-estorno-vendas.md](27-cancelamento-estorno-vendas.md);
- rate limit: [28-rate-limit-redis.md](28-rate-limit-redis.md);
- migrations: [29-migracoes-versionadas.md](29-migracoes-versionadas.md).

## 9. Ponto oficial de retomada

O desenvolvimento posterior deve partir do commit marcado como **`docs: registra versão atual 13/08/2026`** na branch `main`. Mudanças futuras devem indicar explicitamente se afetam Web/API, Windows ou ambos e executar apenas os pipelines correspondentes.
