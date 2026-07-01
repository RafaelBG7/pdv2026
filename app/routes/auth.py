from flask import Blueprint, redirect, render_template, request, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import User


auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        form_type = request.form.get('form_type', 'login')
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if form_type == 'register':
            email = request.form.get('email', '').strip()
            confirm_password = request.form.get('confirm_password', '')

            if not username:
                flash('Informe o usuário para cadastro.', 'danger')
                return render_template('login.html', auth_tab='register')
            if len(password) < 6:
                flash('A senha deve ter pelo menos 6 caracteres.', 'danger')
                return render_template('login.html', auth_tab='register')
            if password != confirm_password:
                flash('A confirmação da senha não confere.', 'danger')
                return render_template('login.html', auth_tab='register')
            if User.query.filter_by(username=username).first():
                flash('Já existe um usuário com este login.', 'danger')
                return render_template('login.html', auth_tab='register')

            user = User(username=username, email=email, role='admin', is_active=True)
            user.set_password(password)
            db.session.add(user)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash('Já existe um usuário com este login.', 'danger')
                return render_template('login.html', auth_tab='register')

            login_user(user)
            flash('Cadastro realizado com sucesso.', 'success')
            return redirect(url_for('main.dashboard'))

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            flash('Login realizado com sucesso.', 'success')
            return redirect(url_for('main.dashboard'))

        flash('Usuário ou senha inválidos.', 'danger')

    return render_template('login.html', auth_tab='login')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/configuracoes', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        form_type = request.form.get('form_type')

        if form_type == 'profile':
            current_user.first_name = request.form.get('first_name', '').strip()
            current_user.last_name = request.form.get('last_name', '').strip()
            current_user.phone = request.form.get('phone', '').strip()
            db.session.commit()
            flash('Dados do usuário atualizados com sucesso.', 'success')
            return redirect(url_for('auth.settings'))

        if form_type == 'email':
            current_user.email = request.form.get('email', '').strip()
            db.session.commit()
            flash('Email atualizado com sucesso.', 'success')
            return redirect(url_for('auth.settings'))

        if form_type == 'password':
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')

            if not current_user.check_password(current_password):
                flash('Senha atual incorreta.', 'danger')
                return redirect(url_for('auth.settings'))
            if len(new_password) < 6:
                flash('A nova senha deve ter pelo menos 6 caracteres.', 'danger')
                return redirect(url_for('auth.settings'))
            if new_password != confirm_password:
                flash('A confirmação da senha não confere.', 'danger')
                return redirect(url_for('auth.settings'))

            current_user.set_password(new_password)
            db.session.commit()
            flash('Senha alterada com sucesso.', 'success')
            return redirect(url_for('auth.settings'))

    return render_template('settings/index.html')
