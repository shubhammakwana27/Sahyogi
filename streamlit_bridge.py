"""Session-isolated access to the existing SAHYOGI HTTP application."""
from dataclasses import dataclass, field
import http.client
from http.cookies import SimpleCookie
from pathlib import Path
from threading import Thread
from urllib.parse import urlencode, urlsplit, urlunsplit


def local_path(value):
    """Only send requests to routes belonging to this application."""
    parts = urlsplit(str(value))
    if parts.scheme or parts.netloc or not parts.path.startswith('/'):
        raise ValueError('Choose a page in this app.')
    if any(char in str(value) for char in ('\r', '\n', '\\')):
        raise ValueError('Choose a page in this app.')
    return urlunsplit(('', '', parts.path, parts.query, ''))


@dataclass
class Page:
    path: str
    status: int
    headers: dict
    body: bytes

    @property
    def text(self):
        return self.body.decode('utf-8', errors='replace')


class Backend:
    """One shared backend and database, with the original route permissions."""

    def __init__(self, database):
        from app import DemoServer
        from store import Store

        self.server = DemoServer(('127.0.0.1', 0), Store(Path(database)))
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


@dataclass
class PortalSession:
    """Keep cookies on the server and private to one Streamlit session."""

    cookie: str = field(default='', repr=False)

    def request(self, backend, method, path, data=None):
        path = local_path(path)
        port = backend.server.server_port
        headers = {'Cookie': self.cookie} if self.cookie else {}
        body = None
        if method.upper() == 'POST':
            headers.update({
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': f'http://127.0.0.1:{port}',
            })
            body = urlencode(data or {})
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=1200)
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            result_headers = dict(response.getheaders())
            result = Page(path, response.status, result_headers, response.read())
        finally:
            connection.close()
        if 'Set-Cookie' in result_headers:
            cookies = SimpleCookie()
            cookies.load(result_headers['Set-Cookie'])
            self.cookie = '; '.join(
                f'{name}={morsel.value}' for name, morsel in cookies.items()
                if morsel.value
            )
        return result

    def page(self, backend, path):
        for _ in range(8):
            response = self.request(backend, 'GET', path)
            if response.status not in {301, 302, 303, 307, 308}:
                return response
            path = local_path(response.headers.get('Location', '/login'))
        raise ValueError('Reopen the sign-in page and try again.')
