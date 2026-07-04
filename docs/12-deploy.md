# 12 - Deploy

## Status Atual

O projeto está pronto para desenvolvimento local com MySQL e pode ser preparado para produção, mas ainda precisa de hardening antes de ficar público na internet.

Já existe:

- `app.py` funcional usando `create_app`.
- Porta padrão `5001`.
- MySQL central e bancos por adega.
- Variáveis de ambiente para conexão.
- Logs de erro em arquivo.
- Backup por adega.

Ainda falta para produção:

- Servidor WSGI dedicado.
- `DEBUG=False`.
- `SECRET_KEY` forte obrigatória.
- HTTPS.
- CSRF.
- Migrações versionadas.
- Rotina externa de backup.
- Política de atualização e restauração.

## Execução Local

```bash
cd /Users/rafaelborges/pdv-adega-jf
source .venv/bin/activate
python app.py
```

Acesse:

```text
http://127.0.0.1:5001
```

Para trocar a porta:

```bash
PORT=5002 python app.py
```

## MySQL

O MySQL precisa estar instalado e rodando.

Banco central padrão:

```text
adega_central
```

Criar manualmente, se necessário:

```sql
CREATE DATABASE adega_central CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Cada adega terá um banco próprio com prefixo configurável:

```text
adega_1_nome_da_adega
adega_2_outra_adega
```

## Variáveis de Ambiente

Modelo em `.env.example`:

```env
SECRET_KEY=troque-esta-chave-em-producao
MYSQL_USER=root
MYSQL_PASSWORD=
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=adega_central
MYSQL_TENANT_DATABASE_PREFIX=adega
MYSQL_TENANT_DATABASE_URL_TEMPLATE=
MYSQL_SERVER_DATABASE_URL=mysql+pymysql://root@127.0.0.1:3306/mysql?charset=utf8mb4
PORT=5001
```

Observação: o projeto não carrega `.env` automaticamente. Exporte as variáveis no terminal ou configure no serviço de deploy.

## Servidor WSGI Recomendado

Para produção, usar Gunicorn ou outro WSGI:

```bash
python -m pip install gunicorn
gunicorn "app:create_app()" --bind 0.0.0.0:5001
```

Em produção, colocar Nginx/Caddy na frente para HTTPS e proxy reverso.

## Checklist de Produção

- Definir `SECRET_KEY` longa e secreta.
- Remover `debug=True` do ambiente de produção.
- Criar usuário MySQL dedicado com permissões controladas.
- Garantir permissão de criar bancos de adega ou provisionar bancos manualmente.
- Ativar HTTPS.
- Restringir acesso ao painel master.
- Configurar backup externo fora da máquina do app.
- Testar restauração de backup.
- Adicionar CSRF.
- Adicionar Alembic/Flask-Migrate.
- Configurar logs persistentes e rotação.

## Acesso na Rede Local

O `app.py` roda com `host='0.0.0.0'`, permitindo acesso por outro dispositivo na mesma rede.

No Mac servidor:

```bash
ipconfig getifaddr en0
```

Em outro dispositivo:

```text
http://IP_DO_SERVIDOR:5001
```
