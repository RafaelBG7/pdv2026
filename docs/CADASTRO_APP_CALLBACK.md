# Retorno ao GiroFy App após cadastro

O cadastro Web continua em `/login?auth_tab=register` e, após a confirmação do e-mail, mantém o redirecionamento Web existente.

No Windows, o botão **Cadastrar** cria localmente um `state` e um `code_verifier`, guarda-os com DPAPI e abre a mesma página com `source=desktop`, `state` e `code_challenge`. O backend conserva esses dados na sessão do navegador durante o cadastro e a confirmação do e-mail.

Após a confirmação, o backend cria um código aleatório de uso único, válido por cinco minutos, e apresenta a página “Conta criada com sucesso”, que tenta abrir:

`girofy://auth/callback?code=<codigo>&state=<state>`

O instalador registra o protocolo `girofy` no perfil do usuário. O App valida protocolo, rota e `state`, recupera o verificador protegido por DPAPI e chama `POST /api/v1/auth/registration-callback/exchange`. O backend valida o desafio PKCE, expiração e uso único. Em sucesso, devolve somente o e-mail/usuário para preencher a tela de login. A senha nunca transita por URL e o usuário ainda precisa digitá-la; isso preserva a verificação de assinatura já existente.

Se o App já estiver aberto, a segunda ativação encaminha o callback para a instância existente por named pipe restrito ao usuário atual. Se não estiver instalado ou não abrir, a página mantém os botões **Abrir GiroFy App** e **Continuar pela Web**.

## Produção e desenvolvimento

- Aplicar a migration central `central_0004` antes de publicar o backend.
- Servir autenticação e troca de código por HTTPS; HTTP só é aceito nas configurações explícitas de desenvolvimento/teste já existentes.
- Gerar o instalador novamente para registrar o protocolo customizado.
- Códigos são armazenados apenas como SHA-256, expiram em cinco minutos e não podem ser reutilizados.

## Arquivos principais

- `app/services/app_registration_service.py`: emissão e troca segura.
- `app/models/app_registration_code.py`: persistência do código temporário.
- `app/templates/app_registration_complete.html`: retorno automático e fallback.
- `desktop_wpf/src/Girofy.Application/ViewModels/LoginViewModel.cs`: PKCE, validação e preenchimento do login.
- `desktop_wpf/src/Girofy.Desktop/App.xaml.cs`: ativação do protocolo e instância já aberta.
- `desktop_wpf/installer/GiroFy.iss`: registro de `girofy://`.
