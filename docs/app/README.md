# Girofy App Windows

O App é um cliente WPF online. Sua estrutura fica em `desktop_wpf`: Presentation/Desktop, Application/ViewModels e Infrastructure/serviços HTTP.

Estado detalhado e critérios de continuidade: [31-estado-atual-17-08-2026.md](../31-estado-atual-17-08-2026.md).

## Funções

- login, refresh/logout e recuperação de senha;
- dashboard, catálogo, vendas, cancelamento, caixa atual/anteriores;
- estoque, contas, relatórios, auditoria e notificações;
- equipe, perfil, senha, empresa, importação/exportação e backup;
- tema claro/escuro e preferências locais.

Tokens são protegidos localmente; dados de negócio não são persistidos como banco paralelo. Sem rede, a operação informa indisponibilidade: não existe sincronização offline. ViewModels devem cancelar/reutilizar carregamentos e nunca implementar cálculos financeiros autoritativos.

O App consome `/api/v1`; uma mudança incompatível exige nova versão de API, não alteração silenciosa. Consulte [paridade](../FEATURE_PARITY.md).

## Build e distribuição

- solução: `desktop_wpf/Girofy.Desktop.sln`;
- runtime: .NET 8, Windows x64;
- testes: `desktop_wpf/tests/Girofy.UnitTests`;
- build: self-contained, single-file e comprimido;
- release: `windows-preview`;
- executável: `https://github.com/RafaelBG7/pdv2026/releases/download/windows-preview/Girofy.exe`.
- instalador preview 0.8.0: `GiroFy-Setup-0.8.0.exe`, gerado com Inno Setup;
- instalação por usuário: `%LocalAppData%\Programs\GiroFy`;
- documentação: [WINDOWS_INSTALLER.md](../WINDOWS_INSTALLER.md).

O App não executa migrations nem inclui MySQL/Python. O Setup 0.8.0 é de desenvolvimento; Code Signing, auto-update e instalador comercial ainda são pendências.

## Tema claro e escuro

O toggle animado sol/lua é reutilizado no login, topbar e configurações. `Colors.xaml` centraliza os recursos Light/Dark; `WindowsThemeService` aplica e persiste a paleta antes da janela aparecer. Detalhes em [THEMING.md](../shared/THEMING.md).
