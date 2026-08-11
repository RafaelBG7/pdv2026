# Security Hardening - Girofy

Data da etapa: 13/07/2026

## Escopo desta etapa

Esta etapa aplicou um hardening incremental, sem reescrever a arquitetura e sem remover funcionalidades existentes. O foco foi reduzir riscos imediatos em formulários, sessões, senhas, headers e endpoints que alteravam estado via `GET`.

## Riscos encontrados

| Severidade | Risco | Status nesta etapa |
|---|---|---|
| Crítico | Formulários e ações sensíveis sem CSRF | Mitigado com token por sessão e validação global de métodos inseguros. |
| Alto | Ações de alteração usando `GET` | Mitigado para logout, acesso master a adega, saída do acesso master e dispensa de notificação. |
| Alto | Senha mínima antiga muito fraca | Mitigado com política central de senha. |
| Alto | Enumeração de usuário por mensagem de login | Mitigado com resposta pública genérica. |
| Alto | `SECRET_KEY` e senha master padrão em produção | Mitigado com bloqueio de inicialização em `APP_ENV=production`. |
| Médio | Cookies sem política explícita por ambiente | Mitigado com `HttpOnly`, `SameSite`, `Secure` em produção e tempo de sessão configurável. |
| Médio | Ausência de CSP e headers complementares | Mitigado com headers centralizados compatíveis com o frontend atual. |
| Resolvido | Rate limit distribuído | Flask-Limiter usa Redis compartilhado entre workers e instâncias. |
| Médio | Operações destrutivas sem reautenticação | Risco residual. |
| Médio | Migrações não versionadas | Risco residual. |
| Médio | Upload/importação precisa de validação mais profunda | Risco residual. |

## Arquivos criados

- `app/security/__init__.py`
- `app/security/csrf.py`
- `app/security/passwords.py`
- `app/templates/errors/400.html`
- `docs/security-hardening.md`

## Arquivos modificados

- `.env.example`
- `README.md`
- `app/__init__.py`
- `app/routes/auth.py`
- `app/routes/catalog.py`
- `app/static/css/style.css`
- `app/static/js/main.js`
- `app/templates/base.html`
- `app/templates/master/companies.html`
- `config.py`
- `docs/02-requisitos.md`
- `docs/09-api.md`
- `docs/14-seguranca.md`
- `docs/15-testes.md`
- `tests/test_routes.py`

## Melhorias implementadas

### CSRF

Foi adicionada proteção CSRF global em `app/security/csrf.py`.

Características:

- token criptograficamente seguro por sessão;
- validação para `POST`, `PUT`, `PATCH` e `DELETE`;
- token exposto no `base.html` via meta tag;
- JavaScript adiciona `_csrf_token` em formulários e `X-CSRFToken` em `fetch`;
- falha retorna HTTP 400 com página amigável;
- falha é registrada no log sem stack trace para o usuário.

Configuração:

```env
CSRF_ENABLED=1
```

Testes:

```bash
rtk .venv/bin/python -m unittest tests.test_routes
```

Validações cobertas:

- requisição sem token é recusada;
- requisição com token válido funciona;
- página de erro não exibe traceback.

### Endpoints críticos migrados para POST

Foram migrados:

- `POST /logout`;
- `POST /master/adegas/<company_id>/acessar`;
- `POST /master/adegas/sair-acesso`;
- `POST /catalogo/produtos/<product_id>/notificacao-estoque`.

Os templates foram atualizados para usar formulários e botões, preservando a experiência visual.

### Política de senha

A validação central fica em `app/security/passwords.py`.

Regras:

- mínimo de 8 caracteres;
- máximo de 128 caracteres por padrão;
- não aceitar somente espaços;
- não aceitar senha igual ao usuário;
- não aceitar senha igual ao e-mail;
- bloquear senhas comuns.

Variáveis:

```env
PASSWORD_MIN_LENGTH=8
PASSWORD_MAX_LENGTH=128
```

Locais integrados:

- cadastro inicial;
- redefinição de senha;
- alteração de senha;
- criação/contratação de funcionário.

### Anti-enumeração no login

Falhas públicas de login agora usam mensagem genérica:

```text
Usuário/e-mail ou senha inválidos.
```

Internamente, a auditoria continua registrando o evento sem expor senha ou token.

### Configuração segura por ambiente

O `app.py` não usa mais `debug=True` fixo. O debug depende de:

```env
FLASK_DEBUG=1
```

Em produção:

```env
APP_ENV=production
FLASK_DEBUG=0
SECRET_KEY=uma-chave-forte
MASTER_DEFAULT_PASSWORD=uma-senha-forte
```

A aplicação recusa iniciar em produção com `SECRET_KEY` padrão ou `MASTER_DEFAULT_PASSWORD=master123`.

### Sessões e cookies

Configurações adicionadas ou revisadas:

- `PERMANENT_SESSION_LIFETIME`;
- `SESSION_COOKIE_HTTPONLY=True`;
- `SESSION_COOKIE_SAMESITE=Lax`;
- `SESSION_COOKIE_SECURE=True` em produção;
- `REMEMBER_COOKIE_HTTPONLY=True`;
- `REMEMBER_COOKIE_SAMESITE=Lax`;
- `REMEMBER_COOKIE_SECURE=True` em produção.

### Headers HTTP

Headers enviados pela factory:

- `X-Content-Type-Options`;
- `X-Frame-Options`;
- `Referrer-Policy`;
- `Permissions-Policy`;
- `Cross-Origin-Opener-Policy`;
- `Cross-Origin-Resource-Policy`;
- `Content-Security-Policy`.

A CSP atual é compatível com os recursos existentes e ainda permite `unsafe-inline` por causa dos templates atuais. Próxima etapa: reduzir scripts/estilos inline e usar nonce ou hashes.

## Novas dependências

Nenhuma dependência nova foi adicionada nesta etapa. A proteção CSRF foi implementada com biblioteca padrão Python e integração Flask própria para evitar bloquear o ambiente local com download de pacote.

## Novas variáveis de ambiente

```env
PASSWORD_MAX_LENGTH=128
CSRF_ENABLED=1
```

Variáveis já existentes e reforçadas na documentação:

```env
APP_ENV=production
FLASK_DEBUG=0
SECRET_KEY=...
MASTER_DEFAULT_PASSWORD=...
SESSION_COOKIE_SECURE=1
SESSION_COOKIE_SAMESITE=Lax
SESSION_LIFETIME_HOURS=8
```

## Como validar manualmente

### CSRF

1. Abra `/login` e veja a meta tag:

```html
<meta name="csrf-token" content="...">
```

2. Faça um `POST` sem `_csrf_token` ou `X-CSRFToken`.
3. O retorno esperado é HTTP 400.

### Cookies e headers

Use:

```bash
curl -I http://127.0.0.1:5003/login
```

Verifique headers como:

- `X-Content-Type-Options`;
- `X-Frame-Options`;
- `Content-Security-Policy`;
- `Referrer-Policy`;
- `Permissions-Policy`.

Em produção HTTPS, verifique também se cookies saem com `Secure`.

### Rotas POST

`GET /logout` deve retornar método não permitido. O logout real deve ser feito por `POST`.

## Comandos de teste

```bash
rtk .venv/bin/python -m unittest tests.test_routes
```

Último resultado desta etapa:

```text
Ran 138 tests in 18.385s
OK
```

## Itens não concluídos nesta etapa

- Monitorar disponibilidade, memória e política de eviction do Redis de rate limit.
- Reautenticação obrigatória para excluir adega, alterar key e restaurar backup.
- Migrações versionadas com Alembic/Flask-Migrate.
- Revisão completa de upload/importação com limite de linhas, MIME e CSV Injection.
- Revisão Docker para usuário não-root e filesystem mais restrito.
- Auditoria extra para tentativas de IDOR e escalada de privilégio.
- CSP estrita sem `unsafe-inline`.
- Dependência de auditoria como `pip-audit` na pipeline.

## Próxima etapa recomendada

1. Validar periodicamente o rate limit Redis com múltiplas réplicas em homologação.
2. Criar confirmação/reautenticação para operações destrutivas.
3. Adicionar testes IDOR específicos por recurso e por tenant.
4. Fortalecer importação/exportação contra arquivos malformados e CSV Injection.
5. Iniciar Alembic/Flask-Migrate para central e tenants.
6. Revisar Docker/OCI para execução não-root e healthchecks mais rígidos.
