"""Pasarela local temporal: expone únicamente health y el webhook de Twilio."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

MAX_BODY = 64 * 1024


class Gateway(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        # No guardar números, contenido de mensajes, firmas ni URL privadas.
        pass

    def do_GET(self):
        if self.path != "/health":
            self.send_error(404)
            return
        self.forward("GET")

    def do_POST(self):
        if self.path != "/api/twilio/webhook":
            self.send_error(404)
            return
        self.forward("POST")

    def forward(self, method):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400)
            return
        if length < 0 or length > MAX_BODY:
            self.send_error(413)
            return
        body = self.rfile.read(length) if method == "POST" else None
        headers = {key: self.headers[key] for key in ("Content-Type", "X-Twilio-Signature") if key in self.headers}
        request = Request("http://127.0.0.1:8000" + self.path, data=body, headers=headers, method=method)
        try:
            response = urlopen(request, timeout=20)
        except HTTPError as exc:
            response = exc
        except URLError:
            self.send_error(502)
            return
        with response:
            content = response.read()
            self.send_response(response.status)
            self.send_header("Content-Type", response.headers.get("Content-Type", "application/octet-stream"))
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8001), Gateway).serve_forever()
