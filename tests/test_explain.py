import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from walletdiffai.core import WalletDiffError
from walletdiffai.explain import explain_local

DEMO = json.loads((Path(__file__).parents[1] / "walletdiffai/data/demo_report.json").read_text())


class ModelHandler(BaseHTTPRequestHandler):
    request = None

    def log_message(self, *_args):
        pass

    def do_POST(self):
        type(self).request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        body = json.dumps({"choices": [{"message": {"content": "Two raw-unit changes were observed."}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ExplainTests(unittest.TestCase):
    def test_non_loopback_url_is_rejected(self):
        with self.assertRaisesRegex(WalletDiffError, "loopback"):
            explain_local(DEMO, "https://example.com", "model")

    def test_loopback_commentary_is_untrusted_and_redacted(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), ModelHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = explain_local(DEMO, f"http://127.0.0.1:{server.server_port}", "tiny-model")
        finally:
            server.shutdown()
            server.server_close()
        self.assertEqual(result["trust"], "untrusted_model_commentary")
        sent = json.dumps(ModelHandler.request)
        self.assertNotIn(DEMO["wallet"], sent)
        self.assertEqual(ModelHandler.request["temperature"], 0)


if __name__ == "__main__":
    unittest.main()
