# 17 - Roadmap

## Versão Atual

Implementado:

- Flask monolítico com templates Jinja2.
- MySQL central e bancos separados por adega.
- Login, logout, cadastro e sessão.
- Verificação de e-mail por código.
- Recuperação de senha por link temporário.
- Cadastro com key ou opção "Não tenho key".
- Bloqueio por assinatura/key vencida ou ausente.
- Painel master para adegas, logs e keys.
- Geração de key Basic/Pro com presets e data customizada.
- Dashboard com venda, lucro, caixa, estoque e contas.
- Produtos, categorias, filtros, kits e estoque mínimo.
- Importação de produtos por planilha em Configurações.
- Exportação CSV para admin.
- Abertura e fechamento de caixa.
- Detalhe de caixas anteriores.
- Registro de venda com autocomplete, desconto, F2/F3 e múltiplos pagamentos.
- Relatórios e gráfico por período.
- Contas a pagar e notificações.
- Equipe com CPF, busca e perfis.
- Taxas de Pix, débito e crédito para cálculo de lucro.
- Backup manual e automático.
- Logs de erro visíveis para o master.
- Movimentação de estoque com histórico rastreável.
- Auditoria de ações críticas.
- Testes automatizados de rotas e regras principais.

## Prioridade Alta

- Implementar CSRF nos formulários.
- Adicionar migrações versionadas com Alembic/Flask-Migrate.
- Criar fluxo de restauração de backup.
- Remover `debug=True` em ambiente de produção.
- Forçar `SECRET_KEY` segura fora do desenvolvimento.

## Operação do PDV

Melhorias recomendadas:

- Cancelamento de venda.
- Estorno.
- Sangria e suprimento de caixa.
- Cadastro de fornecedores.
- Registro de compras.
- Impressão de comprovante.
- Leitor de código de barras.

## Gestão

Melhorias recomendadas:

- Curva ABC de produtos.
- Margem por categoria.
- Relatório de divergência de caixa.
- Relatório de estoque mínimo.
- Ranking de funcionários por venda.
- Controle de metas.
- Comparativo entre períodos.

## SaaS e Assinatura

Melhorias recomendadas:

- Regras reais por plano Basic/Pro.
- Tela de contratação/pagamento real.
- Emissão de cobrança mensal/anual.
- Avisos de vencimento de assinatura.
- Bloqueio progressivo antes do vencimento.
- Histórico de keys e renovações.
- Painel de suporte por adega.

## Segurança e Produção

Melhorias recomendadas:

- HTTPS.
- Rate limit persistente/distribuído no login.
- Política de senha mais forte.
- Proteção do painel master por IP ou segundo fator.
- Logs externos.
- Backups externos.
- Teste de restauração.
- Monitoramento de disponibilidade.

## Integrações Futuras

- Impressoras térmicas.
- TEF.
- Emissão fiscal, se aplicável.
- Integrações externas para relatórios e alertas.
- ERP/contabilidade.
- API pública versionada.

## Mobile/Desktop

Possibilidades:

- PWA para operação em tablet.
- Layout dedicado para celular.
- Scanner por câmera.
- Empacotamento com Electron/Tauri.
