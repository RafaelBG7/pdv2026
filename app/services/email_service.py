import smtplib
from email.message import EmailMessage

from flask import current_app


class EmailAuthenticationError(RuntimeError):
    pass


def configured_sender():
    return (
        current_app.config.get('MAIL_FROM_EMAIL') or
        current_app.config.get('MAIL_SMTP_LOGIN') or
        ''
    )


def render_email_template(template_name, **context):
    return current_app.jinja_env.get_template(template_name).render(**context)


def send_email(to_email, subject, html_body, text_body):
    if current_app.config.get('MAIL_SUPPRESS_SEND'):
        current_app.logger.info('Envio de email suprimido para %s: %s', to_email, subject)
        return True

    server = current_app.config.get('MAIL_SMTP_SERVER')
    port = int(current_app.config.get('MAIL_SMTP_PORT') or 587)
    login = current_app.config.get('MAIL_SMTP_LOGIN')
    password = current_app.config.get('MAIL_SMTP_PASSWORD')
    from_email = configured_sender()
    from_name = current_app.config.get('MAIL_FROM_NAME') or 'SkyGest'

    if not all([server, port, login, password, from_email]):
        raise RuntimeError('Configuração de email incompleta. Verifique MAIL_SMTP_* e MAIL_FROM_EMAIL no .env.')

    # O Gmail exibe senhas de app em blocos com espaços; para SMTP, usamos o valor compacto.
    if 'gmail.com' in str(server).lower():
        password = str(password).replace(' ', '')

    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = f'{from_name} <{from_email}>'
    message['To'] = to_email
    message.set_content(text_body)
    message.add_alternative(html_body, subtype='html')

    with smtplib.SMTP(server, port, timeout=20) as smtp:
        smtp.starttls()
        try:
            smtp.login(login, password)
        except smtplib.SMTPAuthenticationError as error:
            raise EmailAuthenticationError('Gmail recusou o login. Confira o e-mail remetente e a senha de app.') from error
        smtp.send_message(message)

    current_app.logger.info('Email enviado para %s: %s', to_email, subject)
    return True


def send_bulk_email(to_emails, subject, html_body, text_body):
    sent_count = 0
    for to_email in to_emails:
        send_email(to_email, subject, html_body, text_body)
        sent_count += 1
    return sent_count


def send_verification_code_email(user, code):
    html_body = render_email_template('emails/verification_code.html', user=user, code=code)
    text_body = (
        f'Olá, {user.full_name or user.username}.\n\n'
        f'Seu código de verificação é: {code}\n'
        'Este código expira em 15 minutos.\n\n'
        'SkyGest'
    )
    return send_email(user.email, 'Código de verificação da sua conta', html_body, text_body)


def send_password_reset_email(user, reset_url):
    html_body = render_email_template('emails/password_reset.html', user=user, reset_url=reset_url)
    text_body = (
        f'Olá, {user.full_name or user.username}.\n\n'
        f'Use este link para redefinir sua senha: {reset_url}\n'
        'O link expira em 30 minutos.\n\n'
        'SkyGest'
    )
    return send_email(user.email, 'Redefinição de senha', html_body, text_body)


def send_email_change_confirmation(user, new_email, confirmation_url):
    html_body = render_email_template(
        'emails/email_change_confirmation.html',
        user=user,
        new_email=new_email,
        confirmation_url=confirmation_url,
    )
    text_body = (
        f'Olá, {user.full_name or user.username}.\n\n'
        f'Foi solicitada a troca do e-mail da conta para {new_email}.\n'
        f'Confirme pelo link: {confirmation_url}\n'
        'O link expira em 30 minutos.\n\n'
        'Se você não solicitou essa alteração, ignore este e-mail e altere sua senha.\n\n'
        'SkyGest'
    )
    return send_email(user.email, 'Confirme a troca de e-mail da conta', html_body, text_body)


def send_alert_email(company, recipients, alert_title, alert_message, alert_url=None):
    html_body = render_email_template(
        'emails/alert_notification.html',
        company=company,
        alert_title=alert_title,
        alert_message=alert_message,
        alert_url=alert_url,
    )
    text_body = (
        f'Alerta da adega {company.name}\n\n'
        f'{alert_title}\n'
        f'{alert_message}\n'
    )
    if alert_url:
        text_body += f'\nAcesse: {alert_url}\n'
    text_body += '\nSkyGest'
    return send_bulk_email(recipients, f'Alerta crítico: {alert_title}', html_body, text_body)
