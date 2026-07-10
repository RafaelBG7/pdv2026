# 14 - Segurança

## Status Atual

O projeto possui segurança básica funcional para uso local/controlado, mas ainda precisa de hardening antes de produção pública.

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

### Sessão Autenticada

Rotas principais usam `@login_required`.

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

## Não Implementado

### CSRF

Formulários POST ainda não possuem token CSRF.

Recomendação:

- Adicionar Flask-WTF ou proteção CSRF equivalente.
- Incluir token em todos os formulários.

## Recomendações de Produção

- Trocar senha padrão do `master`.
- Definir `SECRET_KEY` forte.
- Rodar com `DEBUG=False`.
- Usar domínio com HTTPS.
- Criar usuário MySQL dedicado.
- Restringir painel master.
- Ativar CSRF.
- Usar rate limit persistente para `/login` e endpoints sensíveis.
- Guardar backups fora do servidor.
- Ampliar auditoria para cancelamentos, estornos e aprovações futuras.
- Monitorar erros 500 e tentativas negadas.
- Configurar certificados de assinatura para os instaladores desktop.
