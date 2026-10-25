import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import influxontv_push as P

TOKEN = "a1" * 32
SECRET = "s3cret"


class Recorder:
    def __init__(self):
        self.calls = []
        self.status = 200
        self.reason = ""

    def __call__(self, token, info, note):
        self.calls.append((token, info, note))
        return self.status, self.reason


class RelayTests(unittest.TestCase):
    def setUp(self):
        self.sender = Recorder()
        self.relay = P.Relay(P.State(None), self.sender, SECRET)
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), P.make_handler(self.relay))
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = "http://127.0.0.1:%d" % self.srv.server_address[1]

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()

    def post(self, path, body, secret=SECRET):
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode(), method="POST")
        if secret is not None:
            req.add_header("Authorization", "Bearer " + secret)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def register(self, platform="ios", token=TOKEN):
        return self.post("/register", {"token": token, "platform": platform, "environment": "sandbox", "name": "Test"})

    def alert(self, level, check="c1", name="Battery %", message="Battery is low"):
        return self.post("/alert", {"_check_id": check, "_check_name": name, "_level": level, "_message": message})

    def test_rejects_wrong_or_missing_secret(self):
        self.assertEqual(self.post("/alert", {}, secret="nope")[0], 401)
        self.assertEqual(self.post("/alert", {}, secret=None)[0], 401)

    def test_register_validates_input(self):
        self.assertEqual(self.register(token="xyz")[0], 400)
        self.assertEqual(self.register(platform="mac")[0], 400)
        code, body = self.register()
        self.assertEqual((code, body["devices"]), (200, 1))

    def test_critical_alert_pushes_with_badge_and_sound_on_ios(self):
        self.register()
        code, body = self.alert("crit")
        self.assertEqual((code, body["sent"]), (200, 1))
        token, info, note = self.sender.calls[0]
        self.assertEqual(token, TOKEN)
        aps = note["payload"]["aps"]
        self.assertEqual(aps["alert"], {"title": "Battery %", "body": "Battery is low"})
        self.assertEqual((aps["badge"], aps["sound"]), (1, "default"))
        self.assertEqual(info["environment"], "sandbox")

    def test_tvos_gets_badge_only(self):
        self.register(platform="tvos")
        self.alert("warn")
        aps = self.sender.calls[0][2]["payload"]["aps"]
        self.assertEqual(aps, {"badge": 1, "content-available": 1})
        self.assertEqual(self.sender.calls[0][2]["priority"], 5)

    def test_same_level_is_not_resent(self):
        self.register()
        self.alert("crit")
        _, body = self.alert("crit")
        self.assertEqual(body["sent"], 0)
        self.assertEqual(len(self.sender.calls), 1)

    def test_badge_counts_active_checks_and_recovery_clears_it(self):
        self.register()
        self.alert("crit", check="a")
        self.alert("warn", check="b", name="Other")
        self.assertEqual(self.sender.calls[-1][2]["payload"]["aps"]["badge"], 2)
        self.alert("ok", check="a")
        last = self.sender.calls[-1][2]["payload"]["aps"]
        self.assertEqual(last["badge"], 1)
        self.assertNotIn("sound", last)          # recoveries are silent
        self.alert("ok", check="b", name="Other")
        self.assertEqual(self.sender.calls[-1][2]["payload"]["aps"]["badge"], 0)

    def test_ok_without_prior_alert_is_ignored(self):
        self.register()
        _, body = self.alert("ok")
        self.assertEqual(body["sent"], 0)
        self.assertEqual(self.sender.calls, [])

    def test_info_and_unknown_levels_do_not_push(self):
        self.register()
        self.assertEqual(self.alert("info")[1]["sent"], 0)
        self.assertEqual(self.alert("unknown", check="z")[1]["sent"], 0)

    def test_dead_token_is_removed(self):
        self.register()
        self.sender.status, self.sender.reason = 410, "Unregistered"
        self.alert("crit")
        self.assertEqual(self.relay.state.devices, {})

    def test_test_endpoint_pushes_to_all_devices(self):
        self.register()
        self.register(platform="tvos", token="b2" * 32)
        _, body = self.post("/test", {})
        self.assertEqual(body["sent"], 2)

    def test_health_needs_no_secret(self):
        with urllib.request.urlopen(self.base + "/health") as r:
            self.assertTrue(json.loads(r.read())["ok"])

    def test_state_survives_restart(self):
        import tempfile, os
        path = os.path.join(tempfile.mkdtemp(), "state.json")
        s = P.State(path)
        s.register(TOKEN, "ios", "sandbox", "iPad")
        self.assertIn(TOKEN, P.State(path).devices)


if __name__ == "__main__":
    unittest.main()
