# 14 - Segurança

## Status Atual

Segurança básica de autenticação existe, mas o projeto precisa de hardening antes de produção.

## Implementado

### Hash de Senha

Senhas são armazenadas com hash:

```python
generate_password_hash(password, method='pbkdf2:sha256')
```

### Sessão Autenticada

Rotas principais usam:

```python
@login_required
```

### ORM

SQLAlchemy reduz risco de SQL Injection em consultas normais.

### Templates

Jinja2 escapa variáveis por padrão, reduzindo risco de XSS em saídas simples.

## Parcialmente Implementado

### Chave Secreta

`SECRET_KEY` pode vir do ambiente, mas há padrão fraco:

```text
adega-jf-secret-key
```

Produção deve sempre definir chave segura.

### Usuário Ativo

Campo `is_active` existe, mas não bloqueia login de forma explícita.

### Perfis

Campo `role` existe, mas não há autorização por perfil.

## Não Implementado

### CSRF

Formulários POST não têm token CSRF.

Recomendação:

- Instalar Flask-WTF.
- Habilitar `CSRFProtect`.
- Adicionar token aos formulários.

### Rate Limiting

Não há limite de tentativas de login.

Recomendação:

- Usar Flask-Limiter.
- Limitar `/login`.

### Recuperação de Senha Segura

Não há fluxo de recuperação.

### Auditoria

Não há registro de ações críticas.

### Criptografia em Repouso

SQLite não é criptografado.

### Backup Seguro

Não há rotina de backup nem criptografia de backup.

### LGPD

Dados pessoais atuais:

- Nome.
- Sobrenome.
- Email.
- Telefone.

Requisitos LGPD pendentes:

- Política de retenção.
- Exclusão/anomização quando aplicável.
- Base legal.
- Controle de acesso por perfil.
- Auditoria de acesso e alterações.
- Proteção de backups.

## Riscos Críticos

| Risco | Impacto | Mitigação |
|---|---|---|
| Cadastro público cria admin | Alto | Remover cadastro público ou exigir convite/admin |
| Senha padrão `admin123` | Alto | Forçar troca no primeiro acesso |
| `DEBUG=True` | Alto | Desativar em produção |
| `SECRET_KEY` padrão | Alto | Definir variável segura |
| Sem CSRF | Alto | Adicionar CSRFProtect |
| Sem autorização por papel | Alto | Implementar `roles_required` |
| Produto pode ser excluído por qualquer usuário autenticado | Médio/Alto | Restringir exclusão |
| Sem auditoria | Médio | Criar tabela de auditoria |
| Bootstrap via CDN | Médio | Avaliar SRI ou assets locais |

## Recomendações de Hardening

1. Corrigir configuração de produção.
2. Remover cadastro público.
3. Forçar troca da senha inicial.
4. Implementar CSRF.
5. Implementar permissões.
6. Implementar rate limiting.
7. Adicionar headers de segurança.
8. Configurar HTTPS.
9. Criar logs e auditoria.
10. Definir backup criptografado.

## Headers Recomendados

- `Content-Security-Policy`.
- `X-Frame-Options`.
- `X-Content-Type-Options`.
- `Referrer-Policy`.
- `Strict-Transport-Security` em HTTPS.

## SQL Injection

Baixo risco nas consultas ORM atuais.

Atenção:

- Migrações manuais usam SQL raw fixo, sem input externo.
- Manter entradas do usuário longe de SQL textual.

## XSS

Risco reduzido por autoescape do Jinja2.

Recomendações:

- Evitar `|safe` com dados de usuário.
- Adicionar CSP.
- Sanitizar qualquer HTML futuro informado por usuário.
