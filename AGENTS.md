@RTK.md

## Regra obrigatoria de entrega

- Toda alteracao deve ser preparada e publicada primeiro em homologacao (`develop`).
- Depois do deploy em homologacao, a alteracao deve ser testada manualmente nesse ambiente.
- E proibido promover, fazer deploy, merge ou qualquer alteracao em producao (`main`) sem autorizacao explicita do usuario, concedida depois do teste manual em homologacao.
- A autorizacao nao pode ser presumida a partir do pedido original de implementacao, de um commit, de um push ou da aprovacao de testes automatizados.
- Somente apos essa autorizacao, promover a mesma alteracao validada para producao e gerar a nova versao correspondente.
- Se ainda nao houver autorizacao, encerrar o trabalho com homologacao pronta/testada e informar que a promocao para producao e a nova versao estao pendentes.
