"""Check public HTTPS login without printing session cookie values."""
import sys
from urllib.request import urlopen

url = sys.argv[1]
if not url.startswith('https://'):
    raise SystemExit('HTTPS URL required')
with urlopen(url, timeout=30) as response:
    if not response.url.startswith('https://'):
        raise SystemExit('HTTPS downgrade')
    assert 'max-age=' in response.headers.get('Strict-Transport-Security', ''), 'HSTS missing'
    cookies = response.headers.get_all('Set-Cookie') or []
    sessions = [cookie for cookie in cookies if cookie.lower().startswith('session=')]
    assert sessions, 'Session cookie missing'
    for cookie in sessions:
        attributes = {part.strip().lower() for part in cookie.split(';')[1:]}
        assert {'secure', 'httponly', 'samesite=lax'} <= attributes, 'Unsafe session attributes'
print('HTTPS, HSTS and session cookie attributes verified.')
