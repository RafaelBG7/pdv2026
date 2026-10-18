# Homologação em host dedicado

A homologação usa uma segunda VM Always Free E2.1.Micro. Produção conserva seu host e os dados originais. O runner HML tem label exclusivo `skygest-hml-oci`; o label `girofy-oci` continua exclusivo de produção.

## Entrega e isolamento

O código de homologação vem de `develop`. O diretório é `/opt/girofy/hml`, com `.env.hml`, banco central e tenants HML, Redis, volumes e backups próprios. O deploy em host dedicado usa `HML_GATEWAY_MODE=external`. O script só dispensa a comparação com o arquivo de produção quando executado no host HML esperado; continua validando todas as regras internas de isolamento. Não copiar credenciais de produção para o host HML.

O gateway HTTPS e DNS públicos precisam apontar para a nova stack antes de considerar a migração concluída. Validar login, sessão, API, catálogo, caixa, relatórios e backup/restauração. Manter a origem íntegra até concluir a validação e resolver qualquer diferença de dados. Antes da troca definitiva, suspender escritas em HML, fazer dump final e restaurá-lo no destino. Parar os containers antigos somente após validar o destino e o acesso público. Nunca remover volumes como parte da troca.

## Ajustes preparados para produção

`docker-compose.production-small-vm.yml` preserva buffer pool de 128 MiB, limita conexões a 64 e desativa performance_schema. A redução deve ser validada com concorrência e pools tenant antes de aplicação; o pico histórico não é previsão de capacidade futura. Desativar performance_schema reduz observabilidade e exige reinício do MySQL. O overlay só deve entrar no comando de deploy de produção após autorização explícita posterior ao teste manual HML. Não é aplicado automaticamente.

O backup usa `nice -n 15` para ceder CPU a tarefas interativas, preservando as opções de consistência e a retenção existente. Isso não limita a carga de leitura no MySQL.

## Situação da execução

Concluído em 18/10/2026: VM dedicada `skygest-hml-01`, restauração dos bancos HML, publicação de `b2baaab` em develop, verificação manual por HTTP com sessão autenticada e troca do encaminhamento público. As 49 tabelas/711 registros da cópia inicial conferiram, incluindo comparação de conteúdo. Um dump final foi gerado com escritas HML suspensas antes da troca. Os containers HML antigos ficaram parados, com volumes e configuração preservados.

O DNS continua no gateway original; somente o encaminhamento de HML foi alterado para o host dedicado por HTTPS, com hostname e cadeia do certificado validados (`proxy_ssl_verify_depth 3`). Produção continua com o mesmo banco, aplicação e versão. O gateway HML normaliza IPs encaminhados somente para o proxy conhecido, evitando confiar em cabeçalhos arbitrários de clientes diretos.

O certificado do backend HML tem renovação webroot e timer próprios. A rota `/.well-known/acme-challenge/` é servida no destino; o gateway encaminha o caminho e os dois aliases HTTP redirecionam para HML. A simulação de renovação para os dois nomes passou. Não reativar o antigo workflow que reinstalava o gateway compartilhado sem considerar essa topologia.

Testes: 311 testes Python locais passaram; workflow HML 39152991746 concluiu testes Python, Windows e deploy no runner dedicado. Login, catálogo, categorias, vendas, relatórios, dependências, HTTPS, HSTS e cookies foram verificados no destino e depois no endereço público. Dashboard e caixa retornavam 500 também na origem; o dashboard falhou ao formatar valor monetário negativo. São limitações preexistentes, não corrigidas nesta migração. Não declarar homologação funcional completa desses dois fluxos.

Após autorização explícita posterior aos testes, `max_connections=64` foi aplicado com SET PERSIST no MySQL de produção, sem reinício. Buffer pool permanece 128 MiB; performance_schema permanece ON. O overlay que desativa performance_schema exige autorização/janela futura e não foi aplicado. A prioridade menor do backup está publicada em HML; promoção desse código e nova versão de produção continuam pendentes de autorização específica.

Nas amostras antes/depois, memória disponível no host original passou de 254 para 407 MiB e swap usada de 1565 para 1232 MiB. São amostras pontuais, não um benchmark. Os processos de aplicação e banco de produção não reiniciaram. Uma sondagem excedeu 10 segundos durante o trabalho; na última rodada 18/18 sondagens de produção responderam 200. HML teve interrupção na cópia final e duas tentativas de troca foram revertidas antes da conclusão. Backups e instruções privadas de reversão foram preservados fora do repositório.

A limpeza automática de auditoria da nova HML ficou desativada durante a migração para preservar o histórico; reavaliar a retenção separadamente. O limite do MySQL de produção pode ser revertido a 151 com SET GLOBAL e RESET PERSIST da variável, sem reinício. Reverter HML depois de novas escritas exige preservar primeiro os dados novos; não apontar cegamente para a cópia antiga.
