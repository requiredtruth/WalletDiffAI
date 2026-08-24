import copy
import json
import unittest
from pathlib import Path

from walletdiffai.abi import allowance, balance_of
from walletdiffai.core import WalletDiffError, validate_spec
from walletdiffai.explain import prompt
from walletdiffai.report import verify

DEMO = json.loads((Path(__file__).parents[1] / "walletdiffai/data/demo_report.json").read_text())


class CoreTests(unittest.TestCase):
    def test_abi_encodings(self):
        owner = "0x0000000000000000000000000000000000000001"
        spender = "0x0000000000000000000000000000000000000003"
        self.assertEqual(balance_of(owner), "0x70a08231" + "0" * 63 + "1")
        self.assertEqual(allowance(owner, spender), "0xdd62ed3e" + "0" * 63 + "1" + "0" * 63 + "3")

    def test_spec_normalizes_and_rejects_ambiguous_blocks(self):
        spec = {"schema_version": 1, "wallet": "0x" + "AB" * 20,
                "from_block": "0x10", "to_block": "0x20", "tokens": [], "allowances": []}
        self.assertEqual(validate_spec(spec)["wallet"], "0x" + "ab" * 20)
        for invalid in ("latest", "0x01", "16", None):
            broken = {**spec, "from_block": invalid}
            with self.assertRaises(WalletDiffError):
                validate_spec(broken)

    def test_duplicate_exposure_is_rejected(self):
        token = {"contract": "0x" + "02" * 20, "label": "TOKEN"}
        spec = {"schema_version": 1, "wallet": "0x" + "01" * 20,
                "from_block": "0x1", "to_block": "0x2", "tokens": [token, token], "allowances": []}
        with self.assertRaisesRegex(WalletDiffError, "unique"):
            validate_spec(spec)

    def test_report_verification_detects_tampering(self):
        self.assertIs(verify(DEMO), DEMO)
        broken = copy.deepcopy(DEMO)
        broken["changes"]["native_balance"]["delta"] = "999"
        with self.assertRaisesRegex(WalletDiffError, "derived"):
            verify(broken)

    def test_prompt_redacts_every_address(self):
        material = json.dumps(prompt(DEMO))
        for address in (DEMO["wallet"], DEMO["from"]["tokens"][0]["contract"],
                        DEMO["from"]["allowances"][0]["spender"]):
            self.assertNotIn(address, material)
        self.assertIn("TOKEN_A_TO_SPENDER_1", material)


if __name__ == "__main__":
    unittest.main()
