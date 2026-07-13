# 14 - Segurança

## Status Atual

O projeto possui segurança funcional para uso controlado e recebeu uma primeira etapa de hardening de aplicação. A base atual cobre autenticação, permissões, isolamento por adega, CSRF, headers de segurança, cookies por ambiente, logs mascarados e auditoria. Ainda existem pontos de produção pública que exigem próximas etapas, principalmente rate limit persistente, migrações versionadas, reautenticação para operações destrutivas e revisão Docker completa.

## Implementado

### Hardening do Servidor OCI

No ambiente online atual, a VM foi configurada com medidas sem custo:

- SSH liberado apenas para o IP administrativo configurado;
- login SSH por senha desativado;
- login SSH do usuário `root` desativado;
- limite de tentativas SSH por conexão;
- fail2ban ativo para SSH;
- UFW com entrada pública apenas para a porta alta do Girofy;
- portas 80 e 443 fechadas enquanto não houver domínio/HTTPS;
- MySQL sem porta pública;
- aplicação Flask acessível apenas pelo proxy Caddy dentro da rede Docker.

O acesso público temporário fica em porta alta:

```text
http://IP_PUBLICO:18080
```

Essa configuração reduz a superfície de ataque, mas ainda não substitui HTTPS e controles de aplicação.

### Hash de Senha

Senhas são armazenadas com hash Werkzeug:

```python
generate_password_hash(password, method='scrypt')
```

### Política de Senha

A validação fica centralizada em `app/security/passwords.py` e é reutilizada em:

- cadastro público;
- recuperação/redefinição de senha;
- alteração de senha nas configurações;
- contratação/criação de funcionário.

Regras atuais:

- mínimo de 8 caracteres;
- máximo configurável, padrão 128 caracteres;
- recusa senha vazia ou formada só por espaços;
- recusa senha igual ao usuário;
- recusa senha igual ao e-mail;
- recusa senhas comuns como `senha123`, `admin123`, `master123` e similares.

As variáveis relevantes são:

```env
PASSWORD_MIN_LENGTH=8
PASSWORD_MAX_LENGTH=128
```

### Sessão Autenticada

Rotas principais usam `@login_required`.

### CSRF

O projeto possui proteção CSRF central em `app/security/csrf.py`.

Funcionamento:

- cada sessão recebe um token aleatório gerado com `secrets.token_urlsafe`;
- o token fica disponível no layout base por `<meta name="csrf-token">`;
- `app/static/js/main.js` injeta `_csrf_token` em formulários não-GET;
- requisições `fetch` com `POST`, `PUT`, `PATCH` ou `DELETE` recebem header `X-CSRFToken`;
- requisições sem token, com token inválido ou de outra sessão retornam HTTP 400;
- falha de CSRF é registrada sem stack trace para o usuário.

Configuração:

```env
CSRF_ENABLED=1
```

Em testes, `WTF_CSRF_ENABLED=False` pode ser usado para manter os testes de rotas focados. A suíte também possui testes específicos com CSRF habilitado.

Ações que alteram estado foram migradas para `POST`:

- `/logout`;
- `/master/adegas/<id>/acessar`;
- `/master/adegas/sair-acesso`;
- `/catalogo/produtos/<id>/notificacao-estoque`.

### Permissões por Perfil

Rotas sensíveis usam:

```python
@permission_required('can_manage_sales')
```

Os perfis atuais são:

- `master`
- `admin`
- `manager`
- `operator`

### Isolamento por Adega

Cada adega possui seu próprio banco MySQL operacional. Isso reduz risco de mistura de produtos, categorias, vendas e caixas entre empresas.

### Bloqueio por Assinatura/Key

Adega sem key ativa, vencida ou inativa é redirecionada para a tela de assinatura.

### Verificação de E-mail

Novos cadastros precisam confirmar o e-mail com código de 6 dígitos enviado por SMTP. O código expira, possui limite de tentativas e é invalidado ao reenviar.

### Recuperação de Senha

O usuário pode solicitar link temporário de redefinição. O token expira em 30 minutos, é armazenado com hash e é invalidado depois de usado.

### Troca de E-mail

Quando a conta já possui e-mail confirmado, a alteração exige confirmação pelo e-mail antigo. O link usa token temporário com hash e expira em 30 minutos.

### Alertas por E-mail

Alertas críticos são configuráveis por adega e por destinatário. Cada envio fica registrado para reduzir repetição do mesmo alerta.

### Logs de Erro

Erros são registrados em `logs/errors.log` com dados sensíveis mascarados.

### Auditoria de Ações

Ações críticas são registradas em `audit_logs` com:

- usuário, perfil e empresa;
- rota, método HTTP, IP, user-agent e request id;
- entidade afetada;
- valores antigos e novos sanitizados;
- mascaramento de senhas, tokens, secrets, API keys e keys de ativação.

Admin/gerente autorizado acessa `/auditoria`; o master do sistema acessa
`/master/auditoria`.

### ORM

SQLAlchemy reduz risco de SQL Injection nas consultas normais.

### Escape de Templates

Jinja2 escapa variáveis por padrão, reduzindo risco de XSS básico.

### Cabeçalhos HTTP

As respostas recebem headers centralizados na factory:

- `X-Content-Type-Options: nosniff`;
- `X-Frame-Options: SAMEORIGIN`;
- `Referrer-Policy`;
- `Permissions-Policy`;
- `Cross-Origin-Opener-Policy`;
- `Cross-Origin-Resource-Policy`;
- `Content-Security-Policy`.

A CSP atual permite recursos próprios e Bootstrap via `cdn.jsdelivr.net`, mantendo compatibilidade com scripts e estilos existentes. A próxima etapa recomendada é reduzir gradualmente `unsafe-inline`.

### Cookies e Ambiente

Configurações principais:

```env
APP_ENV=production
FLASK_DEBUG=0
SESSION_LIFETIME_HOURS=8
SESSION_COOKIE_SECURE=1
SESSION_COOKIE_SAMESITE=Lax
```

Em produção, a aplicação recusa inicializar com `SECRET_KEY` padrão e com `MASTER_DEFAULT_PASSWORD=master123`.

## Parcialmente Implementado

### Chave Secreta

`SECRET_KEY` pode vir do ambiente, mas existe padrão fraco para desenvolvimento:

```text
adega-jf-secret-key
```

Em produção, sempre definir uma chave longa e secreta.

### Logs e Auditoria

Logs de erro e auditoria de negócio existem. Em produção, ainda é recomendável enviar
esses dados para armazenamento externo e monitorado.

### Backup

Backup por adega existe, mas produção deve enviar cópias para local externo.

### Rate Limiting de Login

Existe bloqueio simples em memória após tentativas inválidas de login. Ele protege o uso local/controlado, mas em produção deve ser substituído ou complementado por uma solução persistente, como Flask-Limiter com Redis ou outro armazenamento compartilhado.

## Recomendações de Produção

- Definir `MASTER_DEFAULT_PASSWORD` forte antes da primeira inicialização.
- Definir `SECRET_KEY` forte.
- Rodar com `DEBUG=False`.
- Usar domínio com HTTPS.
- Criar usuário MySQL dedicado.
- Restringir painel master.
- Usar rate limit persistente para `/login` e endpoints sensíveis.
- Exigir confirmação digitada/reautenticação para excluir adega e operações destrutivas.
- Adotar Alembic/Flask-Migrate para migrações versionadas.
- Revisar upload/importação com limites de linhas e validação MIME mais forte.
- Revisar Docker para usuário não-root e imagem final mínima.
- Guardar backups fora do servidor.
- Ampliar auditoria para cancelamentos, estornos e aprovações futuras.
- Monitorar erros 500 e tentativas negadas.
- Configurar certificados de assinatura para os instaladores desktop.
