# 11 - Permissões

## Status Atual

Permissões por perfil não estão implementadas.

O sistema possui:

- Campo `User.role`.
- Valor padrão `admin`.
- Cadastro público que também cria `role='admin'`.
- Uso de `@login_required` para exigir autenticação.

O sistema não possui:

- Decorator de autorização por perfil.
- Verificação de `role` nas rotas.
- Matriz de acesso aplicada.
- Tela administrativa de usuários.
- Bloqueio real por perfil.

## Perfis Recomendados

- Administrador.
- Gerente.
- Supervisor.
- Operador.
- Cliente, se futuramente existir portal externo.

## Matriz Planejada

| Funcionalidade | Administrador | Gerente | Supervisor | Operador | Cliente |
|---|---:|---:|---:|---:|---:|
| Login | Sim | Sim | Sim | Sim | Sim |
| Dashboard | Sim | Sim | Sim | Sim | Parcial |
| Produtos - consultar | Sim | Sim | Sim | Sim | Não |
| Produtos - criar/editar | Sim | Sim | Parcial | Não | Não |
| Produtos - excluir | Sim | Não | Não | Não | Não |
| Categorias - consultar | Sim | Sim | Sim | Sim | Não |
| Categorias - criar/editar | Sim | Sim | Parcial | Não | Não |
| Categorias - excluir | Sim | Não | Não | Não | Não |
| Abrir caixa | Sim | Sim | Sim | Sim | Não |
| Fechar caixa | Sim | Sim | Sim | Sim | Não |
| Registrar venda | Sim | Sim | Sim | Sim | Não |
| Aplicar desconto | Sim | Sim | Sim | Parcial | Não |
| Ver vendas | Sim | Sim | Sim | Parcial | Não |
| Relatórios | Sim | Sim | Sim | Não | Não |
| Configurações próprias | Sim | Sim | Sim | Sim | Sim |
| Configurações do sistema | Sim | Não | Não | Não | Não |
| Usuários e permissões | Sim | Não | Não | Não | Não |

## Regras Recomendadas

- Administrador: acesso total.
- Gerente: acesso operacional e relatórios, sem exclusões críticas.
- Supervisor: acompanha caixa, estoque e vendas, com edição limitada.
- Operador: registra vendas e consulta informações necessárias.
- Cliente: acesso externo futuro, se houver.

## Implementação Recomendada

Criar decorator:

```python
from functools import wraps
from flask import abort
from flask_login import current_user

def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator
```

Aplicar em rotas sensíveis:

- Exclusão de produto.
- Exclusão de categoria.
- Relatórios.
- Administração de usuários.
- Configurações globais.

## Permissões Críticas Ausentes

- Qualquer usuário autenticado pode excluir produtos.
- Qualquer usuário autenticado pode excluir categorias vazias.
- Qualquer usuário autenticado pode abrir e fechar caixa.
- Qualquer usuário autenticado pode ver relatórios.
- Qualquer visitante pode criar uma conta admin pela tela de cadastro.
