# 10 - Autenticação

## Tecnologia

Autenticação baseada em sessão com Flask-Login.

Arquivos:

- `app/extensions.py`.
- `app/routes/auth.py`.
- `app/models/user.py`.

## Login

Rota:

- `GET/POST /login`.

Fluxo:

1. Usuário informa `username` e `password`.
2. Sistema busca `User` por `username`.
3. Sistema chama `user.check_password(password)`.
4. Em sucesso, chama `login_user(user)`.
5. Usuário é redirecionado para `/dashboard`.

## Logout

Rota:

- `GET /logout`.

Fluxo:

1. Exige usuário autenticado.
2. Chama `logout_user()`.
3. Mostra mensagem de saída.
4. Redireciona para `/login`.

## Cadastro

O cadastro é feito na própria rota `/login` quando `form_type='register'`.

Validações:

- `username` obrigatório.
- Senha com pelo menos 6 caracteres.
- Confirmação deve coincidir.
- `username` deve ser único.

Comportamento atual:

- Todo usuário cadastrado recebe `role='admin'`.
- Usuário é autenticado automaticamente após cadastro.

Risco:

- Cadastro público de administradores. Em produção, deve ser removido, protegido por convite ou restrito a administradores.

## Hash de Senha

Arquivo: `app/models/user.py`.

Método:

```python
generate_password_hash(password, method='pbkdf2:sha256')
```

Verificação:

```python
check_password_hash(self.password_hash, password)
```

## Sessão

Flask-Login usa sessão Flask assinada por `SECRET_KEY`.

Configuração atual:

- `SECRET_KEY` pode vir de variável de ambiente.
- Padrão: `adega-jf-secret-key`.

Risco:

- Valor padrão não deve ser usado em produção.

## Expiração

Não há configuração explícita de expiração de sessão permanente.

Status: não implementado.

## Refresh Token

Não aplicável no modelo atual, pois não há autenticação por token ou API JSON.

Status: não implementado.

## JWT

Não implementado.

## Recuperação de Senha

Não implementado.

Não há:

- Solicitação de reset.
- Envio de email.
- Token temporário.
- Expiração de token.

## Proteção de Rotas

Implementada com:

```python
@login_required
```

Rotas protegidas:

- Dashboard.
- Produtos.
- Categorias.
- Vendas.
- Caixa.
- Relatórios.
- Configurações.
- Logout.

## Usuário Inativo

Campo `is_active` existe no modelo.

Status:

- Parcial. O campo é armazenado, mas a lógica de login não bloqueia explicitamente usuários inativos.

## Usuário Inicial

Criado em `create_app()`:

```text
username: admin
password: admin123
role: admin
```

Recomendação:

- Trocar senha imediatamente.
- Permitir configurar senha inicial por variável de ambiente.
- Bloquear criação automática em produção após bootstrap.
