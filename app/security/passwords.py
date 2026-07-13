COMMON_PASSWORDS = {
    '12345678',
    '123456789',
    'password',
    'senha123',
    'senha1234',
    'admin123',
    'master123',
    'qwerty123',
    'girofy123',
}


def validate_password_strength(password, *, username='', email='', min_length=8, max_length=128):
    errors = []
    password = password or ''
    normalized = password.strip()
    username = (username or '').strip().casefold()
    email = (email or '').strip().casefold()
    password_folded = normalized.casefold()

    if len(password) < int(min_length):
        errors.append(f'A senha deve ter pelo menos {min_length} caracteres.')
    if len(password) > int(max_length):
        errors.append(f'A senha deve ter no máximo {max_length} caracteres.')
    if not normalized:
        errors.append('A senha não pode ser vazia ou conter apenas espaços.')
    if username and password_folded == username:
        errors.append('A senha não pode ser igual ao usuário.')
    if email and password_folded == email:
        errors.append('A senha não pode ser igual ao e-mail.')
    if password_folded in COMMON_PASSWORDS:
        errors.append('Escolha uma senha menos comum.')

    return errors

