# 15 - Testes

## Visão Geral

Os testes automatizados ficam em:

```text
tests/test_routes.py
```

Framework:

- `unittest`

Comando recomendado:

```bash
source .venv/bin/activate
python -m unittest discover
```

Ou diretamente:

```bash
.venv/bin/python -m unittest discover
```

## Cobertura Atual

Autenticação e assinatura:

- Login.
- Login com "Lembre de mim" e cookie persistente `remember_token`.
- Logout via `POST` e recusa de `GET /logout`.
- Cadastro.
- Verificação de e-mail.
- Troca de e-mail com confirmação no e-mail antigo.
- Recuperação e redefinição de senha.
- Usuário duplicado.
- Cadastro com e sem key.
- Bloqueio por assinatura/key.
- Ativação.
- Falha pública de login com mensagem genérica para reduzir enumeração.
- Política de senha recusando senhas comuns ou fracas em formulários públicos.

CSRF:

- `POST` sem token recusado com HTTP 400 quando CSRF está habilitado.
- `POST` com token válido da sessão aceito.
- Página de erro de CSRF amigável, sem stack trace ao usuário.

Multiadega:

- Isolamento de empresas.
- Produtos/categorias separados por adega.
- Rotas usando tenant atual.
- Painel master acessando adegas.

Permissões:

- Funcionário comum limitado.
- Gerente/admin com permissões diferentes.
- Rotas protegidas por `permission_required`.
- Abas sensíveis escondidas para funcionário.

Catálogo:

- Produtos.
- Categorias.
- Filtros.
- Menu lateral de categorias.
- Padronização visual de filtros e campos de busca.
- Edição expandida.
- Estoque mínimo.
- Kits.
- Importação.

Vendas:

- Caixa obrigatório.
- Listagem principal limitada ao dia atual.
- Filtros por coluna, vendedor, pagamento, status, valor e busca de venda.
- Venda com múltiplos itens.
- Pagamento misto.
- Desconto.
- Troco.
- Erros sem resetar pedido.
- Baixa de estoque.
- Baixa de estoque por kit.
- Movimentação `initial_stock` no cadastro de produto.
- Entrada e ajuste manual via serviço de estoque.
- Bloqueio de ajuste negativo quando a adega não permite estoque negativo.
- Movimentações de venda e kit vinculadas à venda.

Caixa:

- Abertura.
- Fechamento.
- Validação exata de valor.
- Detalhes de caixa anterior.

Relatórios:

- Períodos automáticos.
- Totais.
- Lucro.
- Produtos mais vendidos.
- Gráfico por período.
- Dia sem vendas e 24 horários vazios.
- Pico diário por quantidade e faturamento.
- Vendas simultâneas e alto volume concentrado na mesma hora.

Financeiro e operação:

- Contas a pagar.
- Notificações.
- Alertas por e-mail.
- Taxas de Pix/débito/crédito.
- Backup.
- Exportação CSV.

Logs:

- Separação entre erro e evento externo de segurança.
- `X-Request-ID` na resposta e no registro.
- Mascaramento de senha, token e API key.
- Exceção não tratada registrada uma única vez.
- Limpeza restrita ao master para os dois arquivos.
- Logs de erro.

Auditoria:

- Mascaramento de senha, token, secret e key.
- Registro de valores antigos e novos.
- Página de auditoria acessível por usuário autorizado.
- Rotas de estoque protegidas por permissão.

## Última Validação Conhecida

Validação feita em 16/07/2026:

```text
Ran 142 tests in 19.963s
OK
```

Também foram validados:

- compilação de sintaxe dos principais arquivos Python;
- contrato agregado do dashboard nativo, incluindo isolamento por adega e ocultação por permissão;
- contratos de abertura, consulta e fechamento de caixa pela API, incluindo concorrência,
  conferência de valores, permissões e isolamento por adega;
- sintaxe XML das telas WPF de dashboard, catálogo e caixa;
- ViewModel nativa de caixa, incluindo abertura, fechamento, preservação do valor após
  erro e limpeza ao encerrar a sessão;
- sintaxe dos scripts OCI e deploy;
- workflow YAML de build desktop;
- workflow YAML de deploy OCI;
- deploy real na VM OCI via `scripts/deploy_oci_app.sh`;
- health check remoto em `/login`;
- validação de que o template publicado na VM não mostra mais acessibilidade no menu do perfil;
- containers Docker do app, MySQL e Caddy em execução;
- bloqueio das portas 80/443 no ambiente sem domínio;
- acesso público apenas pela porta alta `18080`.
- redirecionamento de rotas protegidas para login quando não autenticado.

Comandos usados:

```bash
.venv/bin/python -m unittest discover
bash -n scripts/oci/load_oci_env.sh
bash -n scripts/oci/oci_check.sh
bash -n scripts/oci/oci_create_free_tier_vm.sh
bash -n scripts/oci/oci_harden_network.sh
bash -n scripts/deploy_oci_app.sh
```

Observação: o executável `pytest` não está instalado no ambiente local atual. A suíte oficial do projeto usa `unittest`.

## Quando Adicionar Testes

Adicionar ou atualizar testes sempre que mexer em:

- Permissões.
- Cadastro/login/key.
- Isolamento por adega.
- Venda e estoque.
- Caixa.
- Importação/exportação.
- Backup.
- Rotas do painel master.

## Testes Manuais Recomendados

Após alterações grandes, validar manualmente:

1. Entrar como `master`.
2. Gerar uma key avulsa.
3. Cadastrar uma nova adega com essa key.
4. Cadastrar produto e categoria.
5. Abrir caixa.
6. Realizar venda com F2.
7. Fechar caixa com valor exato.
8. Exportar dados como admin.
9. Entrar como funcionário e conferir restrições.
