import asyncio
import unittest

from fastapi import FastAPI
from rootpath_rehearsal import analyze, rehearse


class ProxyTest(unittest.TestCase):
    def data(self):
        return {
            "public_origin": "https://demo.invalid",
            "prefix": "/edge",
            "scenarios": [
                {
                    "name": "configured",
                    "root_path": "/edge",
                    "strip_prefix": True,
                    "trust_forwarded": True,
                }
            ],
        }

    def test_correct_wiring_routes_docs_and_https_redirect(self):
        r = analyze(self.data())
        self.assertFalse(r["needs_review"], r)
        responses = r["scenarios"][0]["responses"]
        self.assertEqual(responses[0]["location"], "https://demo.invalid/edge/items/")
        self.assertEqual(responses[1]["docs_schema_status"], 200)
        self.assertIn("/edge", responses[2]["openapi_servers"])

    def test_missing_root_path_is_explained(self):
        d = self.data()
        d["scenarios"][0]["root_path"] = ""
        r = analyze(d)
        kinds = {x["kind"] for x in r["scenarios"][0]["findings"]}
        self.assertIn("docs_schema_unreachable", kinds)
        self.assertIn("redirect_escapes_public_base", kinds)

    def test_untrusted_forwarding_redirects_to_internal_origin(self):
        d = self.data()
        d["scenarios"][0]["trust_forwarded"] = False
        r = analyze(d)
        self.assertIn(
            "http://upstream.invalid", r["scenarios"][0]["responses"][0]["location"]
        )
        self.assertTrue(r["needs_review"])

    def test_custom_application_factory_receives_local_requests(self):
        calls = []

        def factory():
            a = FastAPI()

            @a.get("/ready/")
            async def ready():
                calls.append(1)
                return {"ok": True}

            return a

        d = self.data()
        d["probes"] = ["/ready/"]
        r = asyncio.run(rehearse(d, factory))
        self.assertFalse(r["needs_review"])
        self.assertEqual(calls, [1])

    def test_scenarios_do_not_contaminate_openapi_cache(self):
        d = self.data()
        d["scenarios"].append({"name": "wrong", "root_path": ""})
        r = analyze(d)
        self.assertTrue(r["scenarios"][0]["passed"])
        self.assertFalse(r["scenarios"][1]["passed"])

    def test_unknown_route_and_invalid_prefix(self):
        d = self.data()
        d["probes"] = ["/absent"]
        self.assertTrue(analyze(d)["needs_review"])
        d = self.data()
        d["prefix"] = "/edge/../secret"
        with self.assertRaises(ValueError):
            analyze(d)

    def test_credentials_and_external_probe_are_rejected(self):
        d = self.data()
        d["public_origin"] = "https://user:pass@demo.invalid"
        with self.assertRaises(ValueError):
            analyze(d)
        d = self.data()
        d["probes"] = ["//other.invalid"]
        with self.assertRaises(ValueError):
            analyze(d)


if __name__ == "__main__":
    unittest.main()
