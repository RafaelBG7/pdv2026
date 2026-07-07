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
- Logout.
- Cadastro.
- Verificação de e-mail.
- Troca de e-mail com confirmação no e-mail antigo.
- Recuperação e redefinição de senha.
- Usuário duplicado.
- Cadastro com e sem key.
- Bloqueio por assinatura/key.
- Ativação.

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
- Edição expandida.
- Estoque mínimo.
- Kits.
- Importação.

Vendas:

- Caixa obrigatório.
- Venda com múltiplos itens.
- Pagamento misto.
- Desconto.
- Troco.
- Erros sem resetar pedido.
- Baixa de estoque.
- Baixa de estoque por kit.

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

Financeiro e operação:

- Contas a pagar.
- Notificações.
- Alertas por e-mail.
- Taxas de Pix/débito/crédito.
- Backup.
- Exportação CSV.
- Logs de erro.

## Última Validação Conhecida

Validação feita em 05/07/2026:

```text
Ran 81 tests in 10.452s
OK
```

Também foram validados:

- compilação de sintaxe dos principais arquivos Python;
- sintaxe dos scripts OCI e deploy;
- workflow YAML de build desktop;
- workflow YAML de deploy OCI;
- deploy real na VM OCI via `scripts/deploy_oci_app.sh`;
- health check remoto em `/login`;
- login remoto com usuário master;
- containers Docker do app, MySQL e Caddy em execução;
- bloqueio das portas 80/443 no ambiente sem domínio;
- acesso público apenas pela porta alta `18080`.

Comandos usados:

```bash
.venv/bin/python -m unittest discover
bash -n scripts/oci/load_oci_env.sh
bash -n scripts/oci/oci_check.sh
bash -n scripts/oci/oci_create_free_tier_vm.sh
bash -n scripts/oci/oci_harden_network.sh
bash -n scripts/deploy_oci_app.sh
```

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
