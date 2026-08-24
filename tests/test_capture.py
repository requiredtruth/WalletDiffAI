import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from walletdiffai.capture import capture
from walletdiffai.core import WalletDiffError
from walletdiffai.rpc import RpcClient


class RpcHandler(BaseHTTPRequestHandler):
    calls = []
    reorg = False
    fail_calls = False

    def log_message(self, *_args):
        pass

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.calls.append((request["method"], request["params"]))
        method, params = request["method"], request["params"]
        if method == "eth_call" and self.fail_calls:
            response = json.dumps({"jsonrpc": "2.0", "id": request["id"],
                                   "error": {"code": -32000, "message": "missing trie node"}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)
            return
        if method == "eth_chainId":
            result = "0x1"
        elif method == "eth_getBlockByNumber":
            suffix = "f" if self.reorg and len([c for c in self.calls if c[0] == method]) > 2 else ("1" if params[0] == "0x10" else "2")
            result = {"number": params[0], "hash": "0x" + suffix * 64}
        elif method == "eth_getBalance":
            result = "0x64" if params[1] == "0x10" else "0x5a"
        elif method == "eth_getTransactionCount":
            result = "0x2" if params[1] == "0x10" else "0x3"
        elif method == "eth_getCode":
            result = "0x"
        elif method == "eth_call":
            selector = params[0]["data"][2:10]
            value = (10 if params[1] == "0x10" else 12) if selector == "70a08231" else (8 if params[1] == "0x10" else 3)
            result = "0x" + f"{value:064x}"
        response = json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)


class CaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), RpcHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        RpcHandler.calls = []
        RpcHandler.reorg = False
        RpcHandler.fail_calls = False
        self.spec = {"schema_version": 1, "wallet": "0x" + "01" * 20,
                     "from_block": "0x10", "to_block": "0x20",
                     "tokens": [{"contract": "0x" + "02" * 20, "label": "TOKEN"}],
                     "allowances": [{"token": "0x" + "02" * 20,
                                      "spender": "0x" + "03" * 20, "label": "TOKEN_TO_SPENDER"}]}

    def client(self):
        return RpcClient(f"http://127.0.0.1:{self.server.server_port}")

    def test_capture_uses_only_explicit_read_calls(self):
        report = capture(self.client(), self.spec)
        self.assertEqual(report["changes"]["native_balance"]["delta"], "-10")
        self.assertEqual(report["changes"]["tokens"][0]["delta"], "2")
        self.assertEqual(report["changes"]["allowances"][0]["delta"], "-5")
        allowed = {"eth_chainId", "eth_getBlockByNumber", "eth_getBalance",
                   "eth_getTransactionCount", "eth_getCode", "eth_call"}
        self.assertTrue(all(method in allowed for method, _ in RpcHandler.calls))
        for method, params in RpcHandler.calls:
            if method not in {"eth_chainId", "eth_getBlockByNumber"}:
                self.assertIn(params[-1], {"0x10", "0x20"})

    def test_header_change_aborts(self):
        RpcHandler.reorg = True
        with self.assertRaisesRegex(WalletDiffError, "block hash changed"):
            capture(self.client(), self.spec)

    def test_token_rpc_error_is_not_treated_as_zero(self):
        RpcHandler.fail_calls = True
        with self.assertRaisesRegex(WalletDiffError, "-32000"):
            capture(self.client(), self.spec)

    def test_disallowed_rpc_method_fails_before_network(self):
        with self.assertRaisesRegex(WalletDiffError, "not allowed"):
            self.client().call("eth_sendRawTransaction", ["0x00"])


if __name__ == "__main__":
    unittest.main()
