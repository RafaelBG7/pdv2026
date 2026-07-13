# 10 - Autenticação

## Tecnologia

A autenticação usa Flask-Login com sessão de navegador.

Arquivos principais:

- `app/extensions.py`
- `app/routes/auth.py`
- `app/models/user.py`
- `app/models/company.py`
- `app/models/activation_key.py`

## Login

Rota:

- `GET/POST /login`

Fluxo:

1. Usuário informa login e senha.
2. Opcionalmente marca "Lembre de mim".
3. Sistema busca `User.username` ou e-mail.
4. Sistema valida `check_password()`.
5. Se o usuário estiver inativo, o acesso é bloqueado.
6. Se o e-mail ainda não foi confirmado, redireciona para `/verify-email`.
7. Se for `master`, redireciona para o painel master.
8. Se a adega exigir ativação, redireciona para `/assinatura`.
9. Caso contrário, entra no dashboard.

### Lembre de Mim

O formulário de login possui a opção:

```text
Lembre de mim
```

Quando marcada, a chamada `login_user(user, remember=True)` cria o cookie persistente
`remember_token` do Flask-Login. Isso permite que o usuário continue autenticado
mesmo após fechar e reabrir o navegador, enquanto o cookie continuar válido.

Quando a opção não é marcada, o login usa a sessão padrão do navegador.

## Cadastro de Adega

O cadastro fica na própria tela `/login`.

Campos principais:

- Nome da adega.
- Usuário.
- E-mail.
- Senha e confirmação.
- Key de ativação.
- Opção "Não tenho key".

Comportamento:

- Cria `Company`.
- Cria primeiro usuário como `admin` com `email_verified = false`.
- Cria banco MySQL separado da adega.
- Se uma key válida for informada, aplica plano e validade.
- Gera código de 6 dígitos e envia por Gmail SMTP.
- Só libera login depois da confirmação do código em `/verify-email`.
- Se o usuário marcar "Não tenho key" ou deixar sem key, a conta é criada, mas fica bloqueada para uso operacional.

## Verificação de E-mail

Rotas:

- `GET/POST /verify-email`
- `POST /verify-email/resend`

Regras:

- Código numérico de 6 dígitos.
- Expiração em 15 minutos.
- Código anterior é invalidado ao reenviar.
- Reenvio limitado por tempo.
- Login é bloqueado enquanto `email_verified = false`.

## Recuperação de Senha

Rotas:

- `GET/POST /forgot-password`
- `GET/POST /reset-password/<token>`

Regras:

- Token seguro gerado com `secrets.token_urlsafe()`.
- Expiração em 30 minutos.
- Tokens antigos do usuário são invalidados ao solicitar novo link.
- Token é marcado como usado depois da redefinição.

## Troca de E-mail

Rota:

- `GET /confirmar-troca-email/<token>`

Regras:

- Se o usuário já possui e-mail confirmado, a troca envia um link para o e-mail antigo.
- O novo e-mail só é aplicado depois da confirmação pelo e-mail antigo.
- O token expira em 30 minutos.
- Se o usuário ainda não possui e-mail, o primeiro cadastro de e-mail é salvo diretamente.

## Key de Ativação

Modelo:

- `ActivationKey`

Campos principais:

- `key`
- `plan`
- `renews_at`
- `active`
- `used_by_company_id`
- `used_at`

Regras:

- Key avulsa pode ser gerada pelo master.
- Key pode ser vinculada a uma adega no momento da geração.
- Key usada é marcada com empresa e data de uso.
- Key inválida ou vencida não libera uso.
- Adega sem key ativa pode visualizar a tela de ativação, mas não operar.

## Usuário Master do Sistema

Na inicialização, o sistema garante um usuário global:

```text
Usuário: master
Senha: master123
```

Esse usuário administra o SaaS inteiro e não deve ser confundido com o admin de uma adega.

## Admin da Adega

Cada adega pode ter mais de um usuário `admin`.

O admin da adega:

- Gerencia produtos, categorias, vendas, caixa, relatórios e contas.
- Gerencia equipe.
- Acessa financeiro, importação, exportação e backup.
- Não acessa o painel master global, exceto se também for o usuário `master` do sistema.

## Hash de Senha

Senhas são armazenadas com hash:

```python
generate_password_hash(password, method='scrypt')
```

Verificação:

```python
check_password_hash(self.password_hash, password)
```

## Sessão

Flask-Login armazena o identificador do usuário na sessão assinada do Flask.

Configuração importante:

- `SECRET_KEY` deve ser forte em produção.
- A chave padrão existe apenas para desenvolvimento local.
- Sessão persistente depende do cookie `remember_token`, gerado somente quando "Lembre de mim" é marcado.

## Bloqueios de Segurança

O sistema bloqueia:

- Login de usuário inativo.
- Login após muitas tentativas inválidas em curto período.
- Login de usuário com e-mail ainda não confirmado.
- Uso de adega inativa.
- Operação de adega sem assinatura/key ativa.
- Acesso a rotas sem autenticação.
- Acesso a rotas protegidas sem permissão.

## Pendências

- CSRF nos formulários.
- Rate limit persistente/distribuído para produção.
- Política de senha mais forte.
