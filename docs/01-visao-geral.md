# 01 - Visão Geral

## Propósito

O Adega JF é um sistema PDV web local para apoiar a rotina de venda, caixa, estoque e acompanhamento financeiro básico de uma adega ou pequeno comércio.

Ele centraliza:

- Cadastro de produtos e categorias.
- Controle de estoque simples.
- Operação de caixa.
- Registro de vendas.
- Formas de pagamento.
- Relatórios de venda, lucro e produtos vendidos.
- Configurações do usuário autenticado.

## Público-alvo

- Operador de caixa.
- Proprietário ou administrador da adega.
- Responsável por estoque.
- Responsável por suporte e manutenção técnica.
- Futuro time de desenvolvimento.

## Benefícios

- Operação simples em navegador.
- Baixo custo de infraestrutura por usar SQLite local.
- Cadastro e venda no mesmo sistema.
- Redução manual de estoque ao vender.
- Relatórios básicos por período.
- Facilidade para evoluir por estar organizado em blueprints, modelos e templates.

## Problemas Resolvidos

- Controle manual de vendas sem histórico centralizado.
- Falta de visibilidade de estoque baixo.
- Dificuldade de fechar caixa com valor esperado.
- Falta de apuração rápida de lucro por venda/período.
- Dificuldade de consultar produtos, categorias e vendas realizadas.

## Status do Produto

| Área | Status | Observações |
|---|---|---|
| Login e sessão | Implementado | Usa Flask-Login e sessão de navegador |
| Cadastro de usuário | Implementado com risco | Cadastro público cria usuário admin |
| Catálogo | Implementado | Produtos, categorias, filtros, kits simples |
| Estoque | Parcial | Baixa em venda; não há histórico de movimentação |
| Caixa | Implementado | Abertura, fechamento e valor esperado |
| Vendas | Implementado | Itens, desconto, pagamentos, troco e baixa |
| Relatórios | Implementado | Períodos e totais operacionais |
| Permissões | Planejado | Campo `role` existe, mas não restringe rotas |
| API JSON | Não implementado | Rotas são HTML/formulário |
| Auditoria | Não implementado | Sem trilha de alterações |
| Deploy | Parcial | Apenas execução local; `app.py` tem erro de import |
| Backup | Não implementado | Diretórios existem, mas não há rotina |

## Objetivos de Negócio

- Permitir venda rápida e controle básico de estoque.
- Reduzir erros de fechamento de caixa.
- Dar visibilidade de produtos sem estoque ou com estoque baixo.
- Permitir leitura rápida de resultados por período.
- Criar base técnica para evolução do PDV.

## Escalabilidade Futura

O projeto atual é adequado para uso local ou pequeno volume. Para escalar, recomenda-se:

- Migrar SQLite para PostgreSQL.
- Criar migrações versionadas.
- Separar API e frontend, se houver múltiplos clientes.
- Implementar permissões e auditoria.
- Criar filas ou eventos para integrações fiscais, impressão e relatórios.
- Adicionar cache e paginação em listagens quando o catálogo crescer.

## Limitações Atuais Importantes

- `app.py` contém import incorreto de `create_apppy`; a aplicação deve ser iniciada por `flask --app app:create_app run` ou o arquivo deve ser corrigido.
- `DEBUG=True` está definido em `config.py`.
- A chave secreta padrão é fraca para produção.
- Não há proteção CSRF explícita nos formulários.
- Não há bloqueio por perfil.
- Não há logs estruturados.
- Não há backup automático.
- Não há tratamento transacional avançado para concorrência em estoque.
