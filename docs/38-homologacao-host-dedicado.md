# Homologação em host dedicado

A homologação usa uma segunda VM Always Free E2.1.Micro. Produção conserva seu host e os dados originais. O runner HML tem label exclusivo `skygest-hml-oci`; o label `girofy-oci` continua exclusivo de produção.

## Entrega e isolamento

O código de homologação vem de `develop`. O diretório é `/opt/girofy/hml`, com `.env.hml`, banco central e tenants HML, Redis, volumes e backups próprios. O deploy em host dedicado usa `HML_GATEWAY_MODE=external`. O script só dispensa a comparação com o arquivo de produção quando executado no host HML esperado; continua validando todas as regras internas de isolamento. Não copiar credenciais de produção para o host HML.

O gateway HTTPS e DNS públicos precisam apontar para a nova stack antes de considerar a migração concluída. Validar login, sessão, API, catálogo, caixa, relatórios e backup/restauração. Manter a origem íntegra até concluir a validação e resolver qualquer diferença de dados. Antes da troca definitiva, suspender escritas em HML, fazer dump final e restaurá-lo no destino. Parar os containers antigos somente após validar o destino e o acesso público. Nunca remover volumes como parte da troca.

## Ajustes preparados para produção

`docker-compose.production-small-vm.yml` preserva buffer pool de 128 MiB, limita conexões a 64 e desativa performance_schema. A redução deve ser validada com concorrência e pools tenant antes de aplicação; o pico histórico não é previsão de capacidade futura. Desativar performance_schema reduz observabilidade e exige reinício do MySQL. O overlay só deve entrar no comando de deploy de produção após autorização explícita posterior ao teste manual HML. Não é aplicado automaticamente.

O backup usa `nice -n 15` para ceder CPU a tarefas interativas, preservando as opções de consistência e a retenção existente. Isso não limita a carga de leitura no MySQL.

## Situação da execução

VM dedicada criada. Restauração, publicação em develop, teste manual HML, mudança do gateway, desativação da origem e aplicação de ajustes de produção devem ser registrados com suas evidências antes de marcar como concluídos. Nenhuma garantia de ausência de downtime deriva apenas do provisionamento; o reinício de MySQL em produção requer janela curta e autorização.
