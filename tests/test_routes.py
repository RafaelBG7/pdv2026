from datetime import datetime, timedelta
import unittest

from app import create_app
from app.extensions import db
from app.models import CashRegister, Category, Payment, Product, Sale, SaleItem, User


class TestConfig:
    TESTING = True
    SECRET_KEY = 'test-secret-key'
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False


class RouteTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

    def login(self, username='admin', password='admin123', follow_redirects=False):
        return self.client.post(
            '/login',
            data={'username': username, 'password': password},
            follow_redirects=follow_redirects,
        )

    def open_cash_register(self, amount='100,00'):
        return self.client.post('/caixa/abrir', data={'opening_amount': amount}, follow_redirects=True)

    def test_login_page_loads(self):
        response = self.client.get('/login')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Adega JF'.encode(), response.data)
        self.assertIn('Entrar'.encode(), response.data)
        self.assertIn('Cadastrar'.encode(), response.data)

    def test_register_creates_user_and_logs_in(self):
        response = self.client.post(
            '/login',
            data={
                'form_type': 'register',
                'username': 'operador',
                'email': 'operador@example.com',
                'password': 'senha123',
                'confirm_password': 'senha123',
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Cadastro realizado com sucesso.'.encode(), response.data)
        self.assertIn('Dashboard'.encode(), response.data)
        with self.app.app_context():
            user = User.query.filter_by(username='operador').one()
            self.assertEqual(user.email, 'operador@example.com')
            self.assertTrue(user.check_password('senha123'))

    def test_register_rejects_duplicate_username(self):
        response = self.client.post(
            '/login',
            data={
                'form_type': 'register',
                'username': 'admin',
                'email': 'admin2@example.com',
                'password': 'senha123',
                'confirm_password': 'senha123',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Já existe um usuário com este login.'.encode(), response.data)

    def test_dashboard_routes_redirect_anonymous_users_to_login(self):
        for route in ('/', '/dashboard'):
            with self.subTest(route=route):
                response = self.client.get(route)

                self.assertEqual(response.status_code, 302)
                self.assertIn('/login', response.location)

    def test_valid_login_redirects_to_dashboard(self):
        response = self.login()

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/dashboard'))

    def test_valid_login_loads_dashboard_when_following_redirects(self):
        response = self.login(follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('Dashboard'.encode(), response.data)
        self.assertIn('Usuário: admin'.encode(), response.data)

    def test_low_stock_notification_appears_for_authenticated_user(self):
        self.login()

        with self.app.app_context():
            low_product = Product(name='Produto Baixo', sale_price=10, stock_quantity=2, min_stock_quantity=3, active=True)
            db.session.add(low_product)
            db.session.add(Product(name='Produto Sem Estoque', sale_price=10, stock_quantity=0, min_stock_quantity=5, active=True))
            db.session.commit()
            low_product_id = low_product.id

        response = self.client.get('/dashboard')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Alertas'.encode(), response.data)
        self.assertIn('Estoque baixo'.encode(), response.data)
        self.assertIn('Produto Baixo está com 2 un. Mínimo: 3 un.'.encode(), response.data)
        self.assertIn('Produto Sem Estoque está sem estoque. Mínimo: 5 un.'.encode(), response.data)

        dismiss_response = self.client.get(f'/catalogo/produtos/{low_product_id}/notificacao-estoque', follow_redirects=True)

        self.assertEqual(dismiss_response.status_code, 200)
        self.assertNotIn('Produto Baixo está com 2 un. Mínimo: 3 un.'.encode(), dismiss_response.data)
        self.assertIn('Produto Sem Estoque está sem estoque. Mínimo: 5 un.'.encode(), dismiss_response.data)

    def test_invalid_login_stays_on_login_page(self):
        response = self.login(password='senha-errada')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Usuário ou senha inválidos.'.encode(), response.data)
        self.assertIn('Entrar'.encode(), response.data)

    def test_authenticated_user_is_redirected_away_from_login(self):
        self.login()

        response = self.client.get('/login')

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/dashboard'))

    def test_logout_redirects_to_login(self):
        self.login()

        response = self.client.get('/logout', follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('Você saiu do sistema.'.encode(), response.data)
        self.assertIn('Entrar'.encode(), response.data)

    def test_logout_redirects_anonymous_users_to_login(self):
        response = self.client.get('/logout')

        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.location)

    def test_settings_redirect_anonymous_users_to_login(self):
        response = self.client.get('/configuracoes')

        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.location)

    def test_unknown_route_returns_404_page(self):
        response = self.client.get('/rota-inexistente')

        self.assertEqual(response.status_code, 404)

    def test_catalog_routes_redirect_anonymous_users_to_login(self):
        for route in ('/catalogo/produtos', '/catalogo/produtos/novo', '/catalogo/categorias'):
            with self.subTest(route=route):
                response = self.client.get(route)

                self.assertEqual(response.status_code, 302)
                self.assertIn('/login', response.location)

    def test_settings_page_loads_for_authenticated_user(self):
        self.login()

        response = self.client.get('/configuracoes')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Configurações'.encode(), response.data)
        self.assertIn('Usuário'.encode(), response.data)
        self.assertIn('Suporte'.encode(), response.data)
        self.assertIn('Aparência'.encode(), response.data)
        self.assertIn('Light'.encode(), response.data)
        self.assertIn('Dark'.encode(), response.data)
        self.assertIn('Senha criptografada'.encode(), response.data)
        self.assertIn('Email protegido'.encode(), response.data)

    def test_settings_updates_profile_and_email(self):
        self.login()

        profile_response = self.client.post(
            '/configuracoes',
            data={
                'form_type': 'profile',
                'first_name': 'Rafael',
                'last_name': 'Borges',
                'phone': '(11) 99999-0000',
            },
            follow_redirects=True,
        )

        self.assertEqual(profile_response.status_code, 200)
        self.assertIn('Dados do usuário atualizados com sucesso.'.encode(), profile_response.data)

        email_response = self.client.post(
            '/configuracoes',
            data={'form_type': 'email', 'email': 'rafael@example.com'},
            follow_redirects=True,
        )

        self.assertEqual(email_response.status_code, 200)
        self.assertIn('Email atualizado com sucesso.'.encode(), email_response.data)
        self.assertIn('ra***l@example.com'.encode(), email_response.data)
        with self.app.app_context():
            user = User.query.filter_by(username='admin').one()
            self.assertEqual(user.first_name, 'Rafael')
            self.assertEqual(user.last_name, 'Borges')
            self.assertEqual(user.phone, '(11) 99999-0000')
            self.assertEqual(user.email, 'rafael@example.com')

    def test_settings_updates_password_with_current_password(self):
        self.login()

        wrong_response = self.client.post(
            '/configuracoes',
            data={
                'form_type': 'password',
                'current_password': 'errada',
                'new_password': 'nova123',
                'confirm_password': 'nova123',
            },
            follow_redirects=True,
        )

        self.assertEqual(wrong_response.status_code, 200)
        self.assertIn('Senha atual incorreta.'.encode(), wrong_response.data)

        response = self.client.post(
            '/configuracoes',
            data={
                'form_type': 'password',
                'current_password': 'admin123',
                'new_password': 'nova123',
                'confirm_password': 'nova123',
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Senha alterada com sucesso.'.encode(), response.data)
        with self.app.app_context():
            user = User.query.filter_by(username='admin').one()
            self.assertTrue(user.check_password('nova123'))

    def test_reports_redirect_anonymous_users_to_login(self):
        response = self.client.get('/relatorios')

        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.location)

    def test_product_list_loads_for_authenticated_user(self):
        self.login()

        with self.app.app_context():
            db.session.add(Product(name='Produto Lucro', cost_price=6, sale_price=10, stock_quantity=3, active=True))
            db.session.commit()

        response = self.client.get('/catalogo/produtos')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Produtos'.encode(), response.data)
        self.assertIn('Novo produto'.encode(), response.data)
        self.assertIn('Lucro R$ 4,00'.encode(), response.data)
        self.assertIn('40,00%'.encode(), response.data)

    def test_create_edit_toggle_and_delete_product(self):
        self.login()

        create_response = self.client.post(
            '/catalogo/produtos/novo',
            data={
                'name': 'Vinho Tinto',
                'barcode': '789000000001',
                'cost_price': '25,50',
                'sale_price': '39,90',
                'stock_quantity': '12',
                'active': 'on',
            },
            follow_redirects=True,
        )

        self.assertEqual(create_response.status_code, 200)
        self.assertIn('Produto cadastrado com sucesso.'.encode(), create_response.data)
        with self.app.app_context():
            product = Product.query.filter_by(name='Vinho Tinto').first()
            self.assertIsNotNone(product)
            self.assertEqual(product.stock_quantity, 12)
            self.assertEqual(product.sale_price, 39.90)
            product_id = product.id

        edit_response = self.client.post(
            f'/catalogo/produtos/{product_id}/editar',
            data={
                'name': 'Vinho Tinto Reserva',
                'barcode': '789000000001',
                'cost_price': '26,00',
                'sale_price': '44,90',
                'stock_quantity': '10',
                'active': 'on',
            },
            follow_redirects=True,
        )

        self.assertEqual(edit_response.status_code, 200)
        self.assertIn('Produto atualizado com sucesso.'.encode(), edit_response.data)
        self.assertIn('Vinho Tinto Reserva'.encode(), edit_response.data)

        toggle_response = self.client.post(
            f'/catalogo/produtos/{product_id}/alternar-status',
            follow_redirects=True,
        )

        self.assertEqual(toggle_response.status_code, 200)
        self.assertIn('Produto desativado com sucesso.'.encode(), toggle_response.data)
        with self.app.app_context():
            self.assertFalse(db.session.get(Product, product_id).active)

        delete_response = self.client.post(
            f'/catalogo/produtos/{product_id}/excluir',
            follow_redirects=True,
        )

        self.assertEqual(delete_response.status_code, 200)
        self.assertIn('Produto excluído com sucesso.'.encode(), delete_response.data)
        with self.app.app_context():
            self.assertIsNone(db.session.get(Product, product_id))

    def test_create_duplicate_barcode_shows_error(self):
        self.login()

        payload = {
            'name': 'Produto 1',
            'barcode': '123456789',
            'cost_price': '1,00',
            'sale_price': '2,00',
            'stock_quantity': '1',
            'active': 'on',
        }
        self.client.post('/catalogo/produtos/novo', data=payload)
        payload['name'] = 'Produto 2'

        response = self.client.post('/catalogo/produtos/novo', data=payload)

        self.assertEqual(response.status_code, 200)
        self.assertIn('Já existe um produto com este código de barras.'.encode(), response.data)

    def test_product_price_is_saved_as_typed_currency_value(self):
        self.login()

        response = self.client.post(
            '/catalogo/produtos/novo',
            data={
                'name': 'Vodka',
                'barcode': '987654321',
                'cost_price': '20,00',
                'sale_price': '38,00',
                'stock_quantity': '4',
                'active': 'on',
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            product = Product.query.filter_by(name='Vodka').first()
            self.assertIsNotNone(product)
            self.assertEqual(product.sale_price, 38.00)
            self.assertFalse(product.is_kit)
            self.assertIsNone(product.kit_component_product_id)

    def test_kit_product_can_be_created_and_discounts_base_product_stock(self):
        self.login()
        self.open_cash_register()

        with self.app.app_context():
            base_product = Product(
                name='Heineken 269ml (1un)',
                sale_price=6,
                stock_quantity=16,
                active=True,
            )
            db.session.add(base_product)
            db.session.commit()
            base_product_id = base_product.id

        create_response = self.client.post(
            '/catalogo/produtos/novo',
            data={
                'name': 'Heineken 269ml caixa com 8',
                'barcode': 'kit-8',
                'cost_price': '30,00',
                'sale_price': '42,00',
                'stock_quantity': '0',
                'active': 'on',
                'is_kit': 'on',
                'kit_component_product_id': str(base_product_id),
                'kit_component_quantity': '8',
            },
            follow_redirects=True,
        )

        self.assertEqual(create_response.status_code, 200)
        with self.app.app_context():
            kit_product = Product.query.filter_by(name='Heineken 269ml caixa com 8').first()
            self.assertIsNotNone(kit_product)
            self.assertTrue(kit_product.is_kit)
            self.assertEqual(kit_product.effective_stock_quantity, 2)
            kit_product_id = kit_product.id

        sale_response = self.client.post(
            '/vendas/nova',
            data={
                'product_id[]': [str(kit_product_id)],
                'quantity[]': ['1'],
                'payment_money': '42,00',
            },
            follow_redirects=True,
        )

        self.assertEqual(sale_response.status_code, 200)
        self.assertIn('Venda finalizada com sucesso.'.encode(), sale_response.data)
        with self.app.app_context():
            self.assertEqual(db.session.get(Product, base_product_id).stock_quantity, 8)
            self.assertEqual(db.session.get(Product, kit_product_id).stock_quantity, 0)

    def test_kit_sale_requires_enough_base_product_stock(self):
        self.login()
        self.open_cash_register()

        with self.app.app_context():
            base_product = Product(
                name='Heineken unidade',
                sale_price=6,
                stock_quantity=7,
                active=True,
            )
            kit_product = Product(
                name='Heineken kit 8',
                sale_price=42,
                stock_quantity=0,
                active=True,
                is_kit=True,
                kit_component_quantity=8,
            )
            db.session.add_all([base_product, kit_product])
            db.session.flush()
            kit_product.kit_component_product_id = base_product.id
            db.session.commit()
            kit_product_id = kit_product.id

        response = self.client.post(
            '/vendas/nova',
            data={
                'product_id[]': [str(kit_product_id)],
                'quantity[]': ['1'],
                'payment_money': '42,00',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Estoque insuficiente para Heineken unidade.'.encode(), response.data)
        with self.app.app_context():
            self.assertEqual(Sale.query.count(), 0)

    def test_product_can_be_quick_updated_from_expanded_row(self):
        self.login()

        with self.app.app_context():
            product = Product(
                name='Produto Antigo',
                barcode='555',
                cost_price=10,
                sale_price=20,
                stock_quantity=2,
                active=True,
            )
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        response = self.client.post(
            f'/catalogo/produtos/{product_id}/atualizar',
            data={
                'name': 'Produto Novo',
                'barcode': '555',
                'cost_price': '12,00',
                'sale_price': '38,00',
                'stock_quantity': '9',
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Produto atualizado com sucesso.'.encode(), response.data)
        with self.app.app_context():
            product = db.session.get(Product, product_id)
            self.assertEqual(product.name, 'Produto Novo')
            self.assertEqual(product.sale_price, 38.00)
            self.assertEqual(product.stock_quantity, 9)

    def test_category_can_be_created_and_used_by_product(self):
        self.login()

        category_response = self.client.post(
            '/catalogo/categorias',
            data={'name': 'Bebidas'},
            follow_redirects=True,
        )

        self.assertEqual(category_response.status_code, 200)
        self.assertIn('Categoria cadastrada com sucesso.'.encode(), category_response.data)
        self.assertIn('Bebidas'.encode(), category_response.data)

    def test_category_filters_by_search_usage_and_sort(self):
        self.login()

        with self.app.app_context():
            wines = Category(name='Vinhos')
            empty = Category(name='Destilados')
            beers = Category(name='Cervejas')
            db.session.add_all([wines, empty, beers])
            db.session.flush()
            db.session.add_all([
                Product(name='Vinho 1', category_id=wines.id),
                Product(name='Vinho 2', category_id=wines.id),
                Product(name='Cerveja 1', category_id=beers.id),
            ])
            db.session.commit()

        response = self.client.get(
            '/catalogo/categorias',
            query_string={'q': 'vin', 'usage': 'with_products', 'sort': 'products_desc'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Vinhos'.encode(), response.data)
        self.assertNotIn('Destilados'.encode(), response.data)
        self.assertNotIn('Cervejas'.encode(), response.data)

        empty_response = self.client.get('/catalogo/categorias', query_string={'usage': 'empty'})

        self.assertEqual(empty_response.status_code, 200)
        self.assertIn('Destilados'.encode(), empty_response.data)
        self.assertNotIn('Vinhos'.encode(), empty_response.data)

    def test_category_can_be_quick_updated_from_expanded_row(self):
        self.login()

        with self.app.app_context():
            category = Category(name='Antiga')
            db.session.add(category)
            db.session.commit()
            category_id = category.id

        response = self.client.post(
            f'/catalogo/categorias/{category_id}/atualizar',
            data={'name': 'Nova'},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Categoria atualizada com sucesso.'.encode(), response.data)
        with self.app.app_context():
            self.assertEqual(db.session.get(Category, category_id).name, 'Nova')

    def test_product_filters_by_category_stock_price_and_sort(self):
        self.login()

        with self.app.app_context():
            wines = Category(name='Vinhos')
            beers = Category(name='Cervejas')
            db.session.add_all([wines, beers])
            db.session.flush()
            db.session.add_all([
                Product(name='Vinho Barato', category_id=wines.id, sale_price=30, stock_quantity=3, min_stock_quantity=5, active=True),
                Product(name='Vinho Premium', category_id=wines.id, sale_price=120, stock_quantity=8, active=True),
                Product(name='Cerveja Lager', category_id=beers.id, sale_price=8, stock_quantity=0, active=True),
                Product(name='Produto Inativo', category_id=wines.id, sale_price=50, stock_quantity=5, active=False),
            ])
            db.session.commit()
            wines_id = wines.id

        response = self.client.get(
            '/catalogo/produtos',
            query_string={
                'status': 'active',
                'category_id': str(wines_id),
                'stock': 'low',
                'min_price': '20,00',
                'max_price': '80,00',
                'sort': 'price_desc',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Vinho Barato'.encode(), response.data)
        self.assertNotIn('<span>Vinho Premium</span>'.encode(), response.data)
        self.assertNotIn('<span>Cerveja Lager</span>'.encode(), response.data)
        self.assertNotIn('<span>Produto Inativo</span>'.encode(), response.data)

    def test_sales_pages_load_for_authenticated_user(self):
        self.login()
        self.open_cash_register()

        response = self.client.get('/vendas')
        new_response = self.client.get('/vendas/nova')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Realizar venda'.encode(), response.data)
        self.assertEqual(new_response.status_code, 200)
        self.assertIn('Concluir venda'.encode(), new_response.data)
        self.assertIn('Formas de pagamento'.encode(), new_response.data)

    def test_reports_show_sales_totals_for_selected_period(self):
        self.login()
        self.open_cash_register()

        with self.app.app_context():
            product = Product(name='Tequila', cost_price=60, sale_price=100, stock_quantity=5, min_stock_quantity=3, active=True)
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        sale_response = self.client.post(
            '/vendas/nova',
            data={
                'product_id[]': [str(product_id)],
                'quantity[]': ['1'],
                'discount_amount': '10,00',
                'payment_pix': '90,00',
            },
            follow_redirects=True,
        )

        self.assertEqual(sale_response.status_code, 200)

        with self.app.app_context():
            sale_date = Sale.query.one().created_at.date().isoformat()

        response = self.client.get(
            '/relatorios',
            query_string={'period': 'custom', 'start_date': sale_date, 'end_date': sale_date},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Relatórios'.encode(), response.data)
        self.assertIn('Gráfico de vendas'.encode(), response.data)
        self.assertIn('Total vendido por período'.encode(), response.data)
        self.assertIn('Total vendido'.encode(), response.data)
        self.assertIn('R$ 90,00'.encode(), response.data)
        self.assertIn('Descontos'.encode(), response.data)
        self.assertIn('R$ 10,00'.encode(), response.data)
        self.assertIn('Lucro'.encode(), response.data)
        self.assertIn('R$ 30,00'.encode(), response.data)
        self.assertIn('Pix'.encode(), response.data)
        self.assertIn('Tequila'.encode(), response.data)

    def test_reports_auto_periods_use_rolling_date_ranges(self):
        self.login()

        with self.app.app_context():
            product = Product(name='Saquê', cost_price=20, sale_price=50, stock_quantity=6, active=True)
            sale = Sale(
                created_at=datetime.now() - timedelta(days=5),
                total_amount=50,
                final_amount=50,
                payment_status='paid',
            )
            db.session.add_all([product, sale])
            db.session.flush()
            db.session.add_all([
                SaleItem(
                    sale_id=sale.id,
                    product_id=product.id,
                    quantity=1,
                    unit_price=50,
                    unit_cost_price=20,
                    total_price=50,
                    profit_amount=30,
                ),
                Payment(sale_id=sale.id, method='money', amount=50),
            ])
            db.session.commit()

        daily_response = self.client.get('/relatorios', query_string={'period': 'daily'})
        weekly_response = self.client.get('/relatorios', query_string={'period': 'weekly'})
        monthly_response = self.client.get('/relatorios', query_string={'period': 'monthly'})
        annual_response = self.client.get('/relatorios', query_string={'period': 'annual'})

        self.assertEqual(daily_response.status_code, 200)
        self.assertNotIn('Saquê'.encode(), daily_response.data)
        self.assertIn('Saquê'.encode(), weekly_response.data)
        self.assertIn('Últimos 7 dias'.encode(), weekly_response.data)
        self.assertIn('Saquê'.encode(), monthly_response.data)
        self.assertIn('Últimos 30 dias'.encode(), monthly_response.data)
        self.assertIn('Saquê'.encode(), annual_response.data)
        self.assertIn('Último ano'.encode(), annual_response.data)

    def test_create_sale_with_multiple_products_and_payment_methods(self):
        self.login()
        self.open_cash_register()

        with self.app.app_context():
            wine = Product(name='Vinho', sale_price=40, stock_quantity=10, active=True)
            beer = Product(name='Cerveja', sale_price=8, stock_quantity=20, active=True)
            db.session.add_all([wine, beer])
            db.session.commit()
            wine_id = wine.id
            beer_id = beer.id

        response = self.client.post(
            '/vendas/nova',
            data={
                'product_id[]': [str(wine_id), str(beer_id)],
                'quantity[]': ['2', '3'],
                'payment_money': '50,00',
                'payment_pix': '54,00',
                'payment_debit': '',
                'payment_credit': '',
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Venda finalizada com sucesso.'.encode(), response.data)
        self.assertIn('Troco'.encode(), response.data)

        with self.app.app_context():
            sale = Sale.query.one()
            self.assertEqual(round(sale.final_amount, 2), 104.00)
            self.assertIsNotNone(sale.cash_register_id)
            self.assertEqual(SaleItem.query.count(), 2)
            self.assertEqual(Payment.query.count(), 2)
            self.assertEqual(db.session.get(Product, wine_id).stock_quantity, 8)
            self.assertEqual(db.session.get(Product, beer_id).stock_quantity, 17)

    def test_sale_uses_registered_product_price(self):
        self.login()
        self.open_cash_register()

        with self.app.app_context():
            product = Product(name='Licor', sale_price=38.00, stock_quantity=5, active=True)
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        response = self.client.post(
            '/vendas/nova',
            data={
                'product_id[]': [str(product_id)],
                'quantity[]': ['1'],
                'payment_money': '38,00',
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            sale = Sale.query.one()
            self.assertEqual(sale.final_amount, 38.00)

    def test_sale_can_be_finished_with_discount_amount(self):
        self.login()
        self.open_cash_register()

        with self.app.app_context():
            product = Product(name='Vodka', cost_price=6.00, sale_price=10.00, stock_quantity=5, active=True)
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        response = self.client.post(
            '/vendas/nova',
            data={
                'product_id[]': [str(product_id)],
                'quantity[]': ['1'],
                'discount_amount': '1,00',
                'payment_money': '9,00',
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Venda finalizada com sucesso.'.encode(), response.data)
        self.assertIn('Desconto'.encode(), response.data)
        self.assertIn('Lucro'.encode(), response.data)
        self.assertIn('R$ 3,00'.encode(), response.data)
        with self.app.app_context():
            sale = Sale.query.one()
            self.assertEqual(sale.total_amount, 10.00)
            self.assertEqual(sale.discount_amount, 1.00)
            self.assertEqual(sale.final_amount, 9.00)
            sale_item = SaleItem.query.one()
            self.assertEqual(sale_item.unit_cost_price, 6.00)
            self.assertEqual(sale_item.profit_amount, 4.00)

        cash_response = self.client.get('/caixa')

        self.assertEqual(cash_response.status_code, 200)
        self.assertIn('Lucro do caixa'.encode(), cash_response.data)
        self.assertIn('R$ 3,00'.encode(), cash_response.data)

    def test_sale_requires_full_payment(self):
        self.login()
        self.open_cash_register()

        with self.app.app_context():
            product = Product(name='Whisky', sale_price=100, stock_quantity=5, active=True)
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        response = self.client.post(
            '/vendas/nova',
            data={
                'product_id[]': [str(product_id)],
                'quantity[]': ['1'],
                'payment_money': '80,00',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Falta pagar R$ 20,00.'.encode(), response.data)
        self.assertIn(f'value="{product_id}"'.encode(), response.data)
        self.assertIn('value="Whisky"'.encode(), response.data)
        self.assertIn('value="1"'.encode(), response.data)
        self.assertIn('value="80,00"'.encode(), response.data)
        with self.app.app_context():
            self.assertEqual(Sale.query.count(), 0)

    def test_sale_keeps_order_when_stock_is_insufficient(self):
        self.login()
        self.open_cash_register()

        with self.app.app_context():
            product = Product(name='Gin', sale_price=90, stock_quantity=1, active=True)
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        response = self.client.post(
            '/vendas/nova',
            data={
                'product_id[]': [str(product_id)],
                'quantity[]': ['3'],
                'payment_money': '270,00',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Estoque insuficiente para Gin.'.encode(), response.data)
        self.assertIn(f'value="{product_id}"'.encode(), response.data)
        self.assertIn('value="Gin"'.encode(), response.data)
        self.assertIn('value="3"'.encode(), response.data)
        self.assertIn('value="270,00"'.encode(), response.data)
        with self.app.app_context():
            self.assertEqual(Sale.query.count(), 0)

    def test_cash_register_can_be_opened_and_closed(self):
        self.login()

        open_response = self.client.post(
            '/caixa/abrir',
            data={'opening_amount': '150,50'},
            follow_redirects=True,
        )

        self.assertEqual(open_response.status_code, 200)
        self.assertIn('Caixa aberto com sucesso.'.encode(), open_response.data)
        self.assertIn('Realizar venda'.encode(), open_response.data)
        with self.app.app_context():
            cash_register = CashRegister.query.one()
            self.assertEqual(cash_register.status, 'open')
            self.assertEqual(cash_register.opening_amount, 150.50)

        close_response = self.client.post(
            '/caixa/fechar',
            data={'closing_amount': '220,00'},
            follow_redirects=True,
        )

        self.assertEqual(close_response.status_code, 200)
        self.assertIn('O valor está excedido em R$ 69,50. Valor esperado: R$ 150,50.'.encode(), close_response.data)
        with self.app.app_context():
            cash_register = CashRegister.query.one()
            self.assertEqual(cash_register.status, 'open')

        close_response = self.client.post(
            '/caixa/fechar',
            data={'closing_amount': '150,50'},
            follow_redirects=True,
        )

        self.assertEqual(close_response.status_code, 200)
        self.assertIn('Caixa fechado com sucesso.'.encode(), close_response.data)
        with self.app.app_context():
            cash_register = CashRegister.query.one()
            self.assertEqual(cash_register.status, 'closed')
            self.assertEqual(cash_register.closing_amount, 150.50)

    def test_cash_register_closes_only_with_opening_amount_plus_sales(self):
        self.login()
        self.open_cash_register(amount='100,00')

        with self.app.app_context():
            product = Product(name='Rum', cost_price=20, sale_price=50, stock_quantity=5, active=True)
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        sale_response = self.client.post(
            '/vendas/nova',
            data={
                'product_id[]': [str(product_id)],
                'quantity[]': ['1'],
                'payment_money': '50,00',
            },
            follow_redirects=True,
        )

        self.assertEqual(sale_response.status_code, 200)

        wrong_close_response = self.client.post(
            '/caixa/fechar',
            data={'closing_amount': '149,99'},
            follow_redirects=True,
        )

        self.assertEqual(wrong_close_response.status_code, 200)
        self.assertIn('Falta R$ 0,01 para fechar o caixa. Valor esperado: R$ 150,00.'.encode(), wrong_close_response.data)
        with self.app.app_context():
            self.assertEqual(CashRegister.query.one().status, 'open')

        close_response = self.client.post(
            '/caixa/fechar',
            data={'closing_amount': '150,00'},
            follow_redirects=True,
        )

        self.assertEqual(close_response.status_code, 200)
        self.assertIn('Caixa fechado com sucesso.'.encode(), close_response.data)
        with self.app.app_context():
            cash_register = CashRegister.query.one()
            self.assertEqual(cash_register.status, 'closed')
            self.assertEqual(cash_register.closing_amount, 150.00)

    def test_new_sale_requires_open_cash_register(self):
        self.login()

        response = self.client.get('/vendas/nova', follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('Abra o caixa antes de registrar uma venda.'.encode(), response.data)
        self.assertIn('Abrir caixa'.encode(), response.data)


if __name__ == '__main__':
    unittest.main()
