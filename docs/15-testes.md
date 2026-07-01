# 15 - Testes

## Visão Geral

Testes automatizados estão em:

```text
tests/test_routes.py
```

Framework:

- `unittest`.

Banco de teste:

- SQLite em memória: `sqlite://`.

Configuração:

- `TESTING=True`.
- `SECRET_KEY='test-secret-key'`.
- `WTF_CSRF_ENABLED=False`, embora Flask-WTF não esteja em uso.

## Como Executar

```bash
source .venv/bin/activate
python -m unittest
```

Ou:

```bash
python -m unittest tests.test_routes
```

## Cobertura Funcional Atual

Autenticação:

- Carregamento da página de login.
- Cadastro de usuário.
- Bloqueio de username duplicado.
- Login válido.
- Login inválido.
- Redirecionamento de usuário autenticado para dashboard.
- Logout.
- Proteção de rotas anônimas.

Configurações:

- Carregamento da página.
- Atualização de perfil e email.
- Alteração de senha.
- Validação de senha atual.

Catálogo:

- Proteção de rotas.
- Listagem de produtos.
- Criação, edição, inativação e exclusão de produto.
- Código de barras duplicado.
- Salvamento de valores monetários.
- Produto kit e baixa do produto base.
- Bloqueio de kit sem estoque base suficiente.
- Edição rápida.
- Criação de categoria.
- Filtro e ordenação de categoria.
- Edição de categoria.
- Filtro de produtos por categoria, estoque, preço e ordenação.

Vendas:

- Páginas de vendas autenticadas.
- Venda com múltiplos produtos.
- Venda com múltiplas formas de pagamento.
- Uso do preço cadastrado.
- Desconto.
- Lucro.
- Pagamento insuficiente.
- Estoque insuficiente.
- Exigência de caixa aberto.

Caixa:

- Abertura.
- Fechamento.
- Bloqueio de fechamento com valor divergente.
- Fechamento considerando abertura + vendas.

Relatórios:

- Totais por período.
- Lucro.
- Desconto.
- Pagamento.
- Produto vendido.
- Períodos automáticos.

## Lacunas de Teste

- CSRF, quando implementado.
- Permissões por perfil, quando implementadas.
- Usuário inativo.
- Exclusão de categoria com produtos em teste específico.
- Handler 500.
- Concorrência em estoque.
- Paginação futura.
- Testes de frontend com navegador real.
- Testes de acessibilidade.
- Testes de responsividade visual.
- Backup e restauração.
- Migrações.

## Testes de Integração Recomendados

- Fluxo completo: login -> abrir caixa -> cadastrar produto -> vender -> relatório -> fechar caixa.
- Venda de kit com múltiplas unidades.
- Tentativa de venda simultânea do último item em estoque.
- Recuperação de banco a partir de backup.

## Testes de Carga Recomendados

Cenários:

- 10 usuários consultando produtos.
- 5 usuários registrando vendas.
- Catálogo com 10 mil produtos.
- Relatório com 100 mil vendas.

Ferramentas possíveis:

- Locust.
- k6.

## Critérios de Homologação

- Login e logout funcionam.
- Senha inicial foi trocada.
- Produto pode ser cadastrado.
- Caixa abre e fecha.
- Venda baixa estoque corretamente.
- Relatório apresenta a venda.
- Backup foi executado e restaurado em ambiente de teste.
