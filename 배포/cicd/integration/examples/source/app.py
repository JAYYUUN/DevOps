"""이미지 빌드·배포 확인용 간단한 HTTP 서버입니다."""
def response_text():
    return "CI/CD demo is running\n"

if __name__ == "__main__":
    from http.server import BaseHTTPRequestHandler, HTTPServer
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = response_text().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
