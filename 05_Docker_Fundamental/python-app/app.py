from http.server import BaseHTTPRequestHandler, HTTPServer


class HelloHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h1>Hello World from Python</h1>")


if __name__ == "__main__":
    print("python app on port 8000", flush=True)
    HTTPServer(("0.0.0.0", 8000), HelloHandler).serve_forever()
