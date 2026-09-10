(function () {
  'use strict';

  var toggle = document.querySelector('[data-menu-toggle]');
  var nav = document.querySelector('[data-site-nav]');
  var header = document.querySelector('[data-site-header]');
  var reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function closeMenu() {
    if (!toggle || !nav) return;
    toggle.setAttribute('aria-expanded', 'false');
    toggle.querySelector('.sr-only').textContent = 'Abrir menu';
    nav.classList.remove('is-open');
    document.body.classList.remove('menu-open');
  }

  if (toggle && nav) {
    toggle.addEventListener('click', function () {
      var open = toggle.getAttribute('aria-expanded') !== 'true';
      toggle.setAttribute('aria-expanded', String(open));
      toggle.querySelector('.sr-only').textContent = open ? 'Fechar menu' : 'Abrir menu';
      nav.classList.toggle('is-open', open);
      document.body.classList.toggle('menu-open', open);
    });
    nav.querySelectorAll('a').forEach(function (link) { link.addEventListener('click', closeMenu); });
    document.addEventListener('keydown', function (event) { if (event.key === 'Escape') closeMenu(); });
  }

  function updateHeader() { if (header) header.classList.toggle('is-scrolled', window.scrollY > 12); }
  window.addEventListener('scroll', updateHeader, { passive: true });
  updateHeader();
  document.querySelectorAll('[data-current-year]').forEach(function (node) { node.textContent = new Date().getFullYear(); });

  var imageBase = '/static/images/';
  var modules = {
    sales: { number: '01', title: 'Venda com poucos cliques', description: 'Busque produtos, aplique descontos autorizados e finalize com diferentes formas de pagamento.', benefits: ['Busca e carrinho rápidos', 'Descontos em segundos', 'Pagamento flexível ou misto'], image: 'skygest-sales-feature.png?v=20260909-features-v2', alt: 'Tela de vendas do SkyGest com busca, carrinho, desconto e pagamentos' },
    products: { number: '02', title: 'Produtos bem organizados', description: 'Centralize o cadastro, categorias, preços, códigos de barras e kits em uma visão simples.', benefits: ['Busca e filtros', 'Preços, margem e estoque', 'Cadastro de produtos e kits'], image: 'skygest-products-feature.png?v=20260909-features-v2', alt: 'Tela de produtos do SkyGest com busca, filtros e formulário de cadastro' },
    categories: { number: '03', title: 'Categorias sob controle', description: 'Organize os produtos por tipo, marca ou setor e encontre cada grupo com rapidez.', benefits: ['Criação de categorias', 'Busca rápida', 'Filtros e ordenação'], image: 'skygest-categories-feature.png?v=20260909-features-v2', alt: 'Tela de categorias do SkyGest com cadastro, busca e ordenação' },
    stock: { number: '04', title: 'Estoque que acompanha a operação', description: 'Registre entradas e ajustes e consulte a origem de cada movimentação do produto.', benefits: ['Entradas e saídas', 'Filtros avançados', 'Rastreabilidade das movimentações'], image: 'skygest-stock-feature.png?v=20260909-features-v2', alt: 'Tela de estoque do SkyGest com entradas, ajustes e histórico de movimentações' },
    cash: { number: '05', title: 'Caixa organizado do início ao fim', description: 'Acompanhe abertura, movimento, pagamentos e fechamento com os registros da operação.', benefits: ['Controle em tempo real', 'Totais por pagamento', 'Histórico e linha do tempo'], image: 'skygest-cash-register-feature.png?v=20260909-features-v2', alt: 'Tela de caixa do SkyGest com totais, histórico e análise da operação' },
    payables: { number: '06', title: 'Compromissos financeiros visíveis', description: 'Cadastre despesas, filtre vencimentos e acompanhe contas pendentes e pagas.', benefits: ['Cadastro rápido de despesas', 'Filtros por status e período', 'Baixa e reabertura de contas'], image: 'skygest-payables-feature.png?v=20260909-features-v2', alt: 'Tela de contas a pagar do SkyGest com despesas, filtros e baixa de pagamento' },
    reports: { number: '07', title: 'Resultados fáceis de entender', description: 'Consulte períodos, indicadores e gráficos para acompanhar o desempenho do negócio.', benefits: ['Faturamento e lucro', 'Horários e formas de pagamento', 'Análise e ranking de produtos'], image: 'skygest-reports-feature.png?v=20260909-features-v2', alt: 'Tela de relatórios do SkyGest com gráficos, indicadores e rankings' },
    audit: { number: '08', title: 'Rastreabilidade para operar com segurança', description: 'Consulte ações críticas por usuário e módulo e compare as alterações registradas.', benefits: ['Indicadores de atividade', 'Filtros avançados', 'Histórico com antes e depois'], image: 'skygest-audit-feature.png?v=20260909-features-v2', alt: 'Tela de auditoria do SkyGest com filtros, histórico e comparação de alterações' }
  };
  var tabs = Array.from(document.querySelectorAll('[data-tour-tab]'));
  var panel = document.querySelector('[data-tour-panel]');

  function selectTab(tab, focus) {
    var data = modules[tab.dataset.tourTab];
    if (!data || !panel) return;
    tabs.forEach(function (item) {
      var active = item === tab;
      item.classList.toggle('is-active', active);
      item.setAttribute('aria-selected', String(active));
      item.setAttribute('tabindex', active ? '0' : '-1');
    });
    panel.classList.add('is-changing');
    window.setTimeout(function () {
      panel.querySelector('[data-tour-number]').textContent = data.number;
      panel.querySelector('[data-tour-title]').textContent = data.title;
      panel.querySelector('[data-tour-description]').textContent = data.description;
      panel.querySelector('[data-tour-benefits]').innerHTML = data.benefits.map(function (benefit) { return '<li>' + benefit + '</li>'; }).join('');
      var image = panel.querySelector('[data-tour-image]');
      image.src = imageBase + data.image;
      image.alt = data.alt;
      panel.classList.remove('is-changing');
      if (focus) tab.focus();
    }, reducedMotion ? 0 : 180);
  }

  tabs.forEach(function (tab, index) {
    tab.addEventListener('click', function () { selectTab(tab, false); });
    tab.addEventListener('keydown', function (event) {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      var next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
      selectTab(tabs[next], true);
    });
  });

  var reveals = document.querySelectorAll('.reveal');
  if (reducedMotion || !('IntersectionObserver' in window)) {
    reveals.forEach(function (item) { item.classList.add('is-visible'); });
  } else {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) { entry.target.classList.add('is-visible'); observer.unobserve(entry.target); }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -30px' });
    reveals.forEach(function (item) { observer.observe(item); });
  }
}());
