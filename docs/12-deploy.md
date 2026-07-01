# 12 - Deploy

## Status Atual

O projeto está preparado para execução local de desenvolvimento, mas não está pronto para produção sem ajustes.

Problemas principais:

- `app.py` contém import incorreto (`create_apppy`).
- `DEBUG=True`.
- `SECRET_KEY` padrão fraca.
- Sem servidor WSGI configurado.
- Sem Docker.
- Sem HTTPS.
- Sem backup.
- Sem migrações formais.

## Execução Local Recomendada

Enquanto `app.py` não for corrigido:

```bash
cd /Users/rafaelborges/pdv-adega-jf
source .venv/bin/activate
flask --app app:create_app run --host 0.0.0.0 --port 5001
```

Após corrigir `app.py`:

```bash
python app.py
```

## Correção Necessária em `app.py`

Atual:

```python
from app import create_apppy
```

Correto:

```python
from app import create_app
```

## Variáveis de Ambiente

Produção deve definir:

```bash
export SECRET_KEY="valor-longo-aleatorio-e-seguro"
export PORT=5001
```

Recomendado adicionar:

```bash
export FLASK_ENV=production
```

E alterar `Config.DEBUG` para depender de variável de ambiente.

## Deploy WSGI Sugerido

Instalar Gunicorn:

```bash
python -m pip install gunicorn
```

Executar:

```bash
gunicorn "app:create_app()" --bind 0.0.0.0:5001
```

Observação:

- Gunicorn não é listado em `requirements.txt` atualmente.

## Nginx Sugerido

Exemplo conceitual:

```nginx
server {
    listen 80;
    server_name pdv.local;

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Banco de Dados

SQLite atual:

```text
database/adega_jf.db
```

Recomendações:

- Garantir permissão de escrita para o usuário do processo.
- Fazer backup antes de deploy.
- Evitar múltiplos processos escrevendo intensamente no mesmo SQLite.
- Considerar PostgreSQL para produção multiusuário.

## Checklist de Produção

- Corrigir `app.py`.
- Desativar `DEBUG`.
- Configurar `SECRET_KEY`.
- Remover ou proteger cadastro público.
- Trocar senha padrão.
- Adicionar CSRF.
- Configurar backup automático.
- Configurar logs.
- Adicionar handler 500.
- Configurar HTTPS.
- Versionar migrações.
- Adicionar servidor WSGI ao `requirements.txt`.
- Criar rotina de restauração testada.

## Rollback

Procedimento recomendado:

1. Parar aplicação.
2. Restaurar versão anterior do código.
3. Restaurar backup do banco, se houve alteração de schema.
4. Reiniciar aplicação.
5. Validar login, catálogo, caixa e venda de teste.

Sem migrações versionadas, rollback de schema precisa ser manual.
