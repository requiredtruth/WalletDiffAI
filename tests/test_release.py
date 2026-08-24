import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


class ReleaseTests(unittest.TestCase):
    def test_support_addresses_are_exact(self):
        support = (ROOT / "SUPPORT.md").read_text()
        expected = {
            "bc1qh474jpyw4malh0fmg2uy7n05ggtjvnjtcwhdne",
            "0x8fcC9C0d1FFCE17b1dEC91B299E56d66BC126Ba8",
            "D6qp2awRAHVo2VgincTAW5frhnJ9MBZcz4",
        }
        for value in expected:
            self.assertEqual(support.count(value), 1)
        self.assertIn("does not purchase support, ownership, returns", support)

    def test_public_sources_contain_no_private_project_marker(self):
        marker = "World" + "Forge"
        for path in ROOT.rglob("*"):
            if path.is_file() and ".git" not in path.parts and "__pycache__" not in path.parts and path.name != "LICENSE":
                self.assertNotIn(marker, path.read_text(errors="ignore"), str(path))

    def test_cli_demo_and_verify(self):
        demo = ROOT / "walletdiffai/data/demo_report.json"
        verified = subprocess.run([sys.executable, "-m", "walletdiffai", "verify", str(demo)],
                                  cwd=ROOT, text=True, capture_output=True, check=True)
        self.assertEqual(verified.stdout, "report verified\n")
        shown = subprocess.run([sys.executable, "-m", "walletdiffai", "demo"],
                               cwd=ROOT, text=True, capture_output=True, check=True)
        self.assertIn("native delta=-25", shown.stdout)
        self.assertNotIn("\x1b", shown.stdout)

    def test_prompt_output_is_canonical_json(self):
        demo = ROOT / "walletdiffai/data/demo_report.json"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "prompt.json"
            subprocess.run([sys.executable, "-m", "walletdiffai", "prompt", str(demo), str(output)],
                           cwd=ROOT, check=True)
            data = json.loads(output.read_text())
            self.assertEqual(data["messages"][0]["role"], "system")
            self.assertTrue(output.read_bytes().endswith(b"\n"))


if __name__ == "__main__":
    unittest.main()
