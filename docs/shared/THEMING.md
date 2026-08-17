# Sistema de temas do Girofy

Web e App oferecem temas claro e escuro com a mesma identidade visual, mas usam mecanismos nativos de cada plataforma. A preferência é local e não altera banco, tenant ou regra de negócio.

## Web

- Tokens ficam em `app/static/css/style.css`, em `:root` e `[data-theme='dark']`.
- Um script pequeno no `<head>` de `base.html` consulta `girofy-theme` antes da pintura, evitando flash branco.
- Sem preferência salva, `prefers-color-scheme` escolhe o estado inicial.
- O toggle sol/lua fica na topbar e também aparece no login; troca o tema sem reload e persiste em `localStorage`.
- Movimento do indicador, rotação/fade dos ícones e cores usam transições de 180–240 ms. `prefers-reduced-motion` reduz o efeito por acessibilidade.
- O seletor textual das configurações e menu do usuário continua sincronizado com o toggle.

## App Windows

- `Themes/Colors.xaml` é o `ResourceDictionary` único de tokens e estilos compartilhados.
- `WindowsThemeService` aplica as paletas Light/Dark nos mesmos brushes e salva a escolha no `JsonUserPreferencesStore`.
- A inicialização carrega a preferência antes de abrir a janela principal; falhas usam o tema escuro padrão sem impedir a abertura.
- `ThemeToggleButtonStyle` é reutilizado no login, topbar autenticada e configurações. O indicador desliza e o sol gira em 240 ms.
- DataGrid, cabeçalho, linhas alternadas, seleção, overlays, estados semânticos, inputs, ComboBox, DatePicker, botões e scrollbars usam recursos de tema.

## Tokens principais

As plataformas mantêm equivalentes para fundo principal/secundário, superfície, superfície elevada, hover, bordas, texto primário/secundário, marca, destaque, sucesso, aviso, erro, cabeçalho de tabela, linha alternada, seleção e overlay.

Ao criar uma tela, use os tokens existentes. Uma cor literal só é aceitável para imagem de marca ou sombra neutra que funcione nos dois temas. Novos tokens devem ser adicionados às duas paletas e documentados aqui.

## Validação

Verifique login, dashboard, venda, produtos/categorias, estoque, caixa, contas, relatórios, auditoria, notificações e configurações em Light e Dark. Confirme persistência após refresh/reabertura, foco por teclado, hover, pressed, disabled, contraste e ausência de superfícies fixas incompatíveis.
