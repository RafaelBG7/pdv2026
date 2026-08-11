# Rate limit persistente e distribuído

## Visão geral

O Girofy usa Flask-Limiter com Redis para compartilhar contadores entre processos e futuras
instâncias do backend. A Web e a API usam a mesma extensão, sem os antigos dicionários locais
de tentativas. O aplicativo Windows não implementa bloqueio próprio: ele recebe HTTP 429 da API.

```text
Web / Windows → Caddy → Flask-Limiter → Redis interno
```

## Ambientes

- Produção: `RATELIMIT_STORAGE_URI` deve apontar para Redis. `memory://` e fallback silencioso
  são recusados durante a inicialização.
- Desenvolvimento: `memory://` é permitido e o limitador pode ser desativado.
- Testes gerais: o limitador fica desativado; testes dedicados usam storage isolado.

## Limites padrão

| Escopo | Padrão | Chave |
|---|---:|---|
| Login Web/API | 5/min e 20/h | IP + hash do identificador normalizado |
| Recuperação de senha | 3/15 min | IP + hash do identificador |
| Reenvio de confirmação | 3/15 min | IP |
| Cadastro de adega | 3/h | IP |
| Ativação por key | 5/15 min | IP+identificador na API; empresa+usuário na Web |
| Refresh token | 120/h | IP + hash do refresh token |
| API geral | 600/min | hash do Bearer token; IP antes da autenticação |
| Importação | 5/h | empresa+usuário |
| Backup manual | 3/h | empresa+usuário |
| Exportação API | 20/h | empresa+usuário |
| Operações master protegidas | 30/h | empresa+usuário |

Todos os valores são configuráveis. Tokens, senhas, keys e cookies nunca entram nos logs;
valores usados em chaves são reduzidos a SHA-256 e não são expostos.

## Respostas e falhas

A Web retorna página amigável com HTTP 429. A API mantém o envelope JSON existente e usa
`rate_limit_exceeded`. Ambas retornam `Retry-After` e `Cache-Control: no-store`.

Quando o Redis fica indisponível, rotas protegidas falham fechadas com HTTP 503,
`Retry-After: 30` e, na API, `rate_limit_unavailable`. Não existe fallback silencioso em produção.

## Proxy e IP real

`ProxyFix` só é ativado com `TRUST_PROXY_HEADERS=1` e confia na quantidade exata definida em
`TRUSTED_PROXY_COUNT`. No Compose oficial há um Caddy. A porta Flask fica em `127.0.0.1`,
impedindo acesso externo direto capaz de injetar `X-Forwarded-For`.

## Redis no Docker/OCI

O Compose usa `redis:7.4.2-alpine`, sem porta publicada, persistência desativada, limite de 96 MB
e política `allkeys-lru`. O container é read-only, perde capacidades Linux e possui health check.

## Health check e logs

- `/health` permanece mínimo para compatibilidade.
- `/health/dependencies` e `/api/v1/health/dependencies` informam apenas `database` e `redis`.
- Bloqueios e falhas do storage vão para `logs/security.log`, com contexto seguro e request-id.
- Esses eventos não vão para `audit_logs`, evitando amplificação durante ataques.

## Testes

```bash
python -m unittest tests.test_routes
docker compose -f docker-compose.oci.yml config --quiet
```

A cobertura dedicada valida 429 Web/API, separação por IP, `Retry-After`, redaction do log,
ProxyFix confiável, Redis indisponível, health e desativação local. Na homologação distribuída,
duas réplicas Flask devem apontar para o mesmo Redis e consumir o mesmo contador.
