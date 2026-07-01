# Adega JF - PDV Local

Este projeto é o esqueleto inicial de um sistema PDV web local para a Adega JF, com foco em simplicidade, organização e evolução gradual.

## Estrutura inicial

- Flask para a aplicação web
- SQLite para armazenamento local
- SQLAlchemy para modelagem de dados
- Flask-Login para autenticação
- Bootstrap 5 para interface básica
- Blueprints para separar rotas

## Requisitos

- Python 3.10+
- pip

## Instalação

```bash
cd pdv-adega-jf
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Execução

```bash
source .venv/bin/activate
python app.py
```

A aplicação ficará disponível em:

- http://localhost:5001

Se precisar usar outra porta:

```bash
PORT=5002 python app.py
```

## Acesso inicial

- Usuário: admin
- Senha: admin123

## Observações

- O banco SQLite é criado automaticamente na primeira execução.
- O usuário administrador inicial é criado automaticamente caso ainda não exista.
- A estrutura está preparada para receber módulos como estoque, vendas, caixa e relatórios.
