"""Check public HTTPS login without printing session cookie values."""
import sys
from urllib.request import HTTPRedirectHandler, build_opener


class HTTPSRedirectHandler(HTTPRedirectHandler):
    # Python 3.10 on the deployment host does not implement HTTP 308.
    http_error_308 = HTTPRedirectHandler.http_error_302

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith('https://'):
            raise ValueError('HTTPS downgrade refused')
        return super().redirect_request(req, fp, 307 if code == 308 else code,
                                        msg, headers, newurl)


def check_headers(url):
    if not url.startswith('https://'):
        raise ValueError('HTTPS URL required')
    with build_opener(HTTPSRedirectHandler()).open(url, timeout=30) as response:
        if not response.url.startswith('https://'):
            raise ValueError('HTTPS downgrade')
        assert 'max-age=' in response.headers.get('Strict-Transport-Security', ''), 'HSTS missing'
        cookies = response.headers.get_all('Set-Cookie') or []
        sessions = [cookie for cookie in cookies if cookie.lower().startswith('session=')]
        assert sessions, 'Session cookie missing'
        for cookie in sessions:
            attributes = {part.strip().lower() for part in cookie.split(';')[1:]}
            assert {'secure', 'httponly', 'samesite=lax'} <= attributes, 'Unsafe session attributes'
    print('HTTPS, HSTS and session cookie attributes verified.')


if __name__ == '__main__':
    check_headers(sys.argv[1])
