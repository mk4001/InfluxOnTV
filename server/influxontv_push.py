#!/usr/bin/env python3
"""InfluxOnTV push relay.

Receives InfluxDB notification-rule POSTs (HTTP notification endpoint) and forwards them as Apple
push notifications (APNs) to the iPad / iPhone / Apple TV devices that registered with it, so alerts
reach the devices even when the app is closed.

    InfluxDB --POST /alert--> this relay --HTTP/2--> APNs --> devices
    App      --POST /register--> this relay

Only Python 3.9+ and, for real pushes, `httpx[http2]` and `PyJWT[crypto]` (see requirements.txt).
"""
from __future__ import annotations

import argparse
import hmac
import json
import logging
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger("influxontv-push")

ACTIVE_LEVELS = {"crit", "warn"}
TOKEN_RE = re.compile(r"^[0-9a-fA-F]{64,200}$")
APNS_HOSTS = {"production": "https://api.push.apple.com", "sandbox": "https://api.sandbox.push.apple.com"}


# MARK: - Persistence -------------------------------------------------------------------------------------------

class State:
    """Registered devices and the last known level of each check, kept in a small JSON file."""

    def __init__(self, path: Optional[str]) -> None:
        self.path = path
        self.lock = threading.RLock()
        self.devices: Dict[str, Dict[str, Any]] = {}
        self.levels: Dict[str, Dict[str, Any]] = {}
        if path and os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                self.devices = data.get("devices", {})
                self.levels = data.get("levels", {})
            except (OSError, ValueError):
                log.warning("could not read %s, starting empty", path)

    def save(self) -> None:
        if not self.path:
            return
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"devices": self.devices, "levels": self.levels}, f, indent=1)
        os.replace(tmp, self.path)

    def register(self, token: str, platform: str, environment: str, name: str) -> None:
        with self.lock:
            self.devices[token.lower()] = {"platform": platform, "environment": environment, "name": name,
                                           "updated": int(time.time())}
            self.save()

    def remove(self, token: str) -> None:
        with self.lock:
            if self.devices.pop(token.lower(), None) is not None:
                self.save()

    def active_count(self) -> int:
        with self.lock:
            return sum(1 for v in self.levels.values() if v["level"] in ACTIVE_LEVELS)


# MARK: - APNs ---------------------------------------------------------------------------------------------------

Sender = Callable[[str, Dict[str, Any], Dict[str, Any]], Tuple[int, str]]
"""(device_token, device_info, notification) -> (http_status, reason). `notification` has push_type, priority, payload."""


class ApnsSender:
    """Token-based (.p8) APNs client. HTTP/2 via httpx, ES256 JWT via PyJWT (imported lazily)."""

    def __init__(self, key_path: str, key_id: str, team_id: str, topic: str) -> None:
        import httpx  # noqa: PLC0415
        self._httpx = httpx
        with open(key_path) as f:
            self._key = f.read()
        self.key_id, self.team_id, self.topic = key_id, team_id, topic
        self._clients: Dict[str, Any] = {}
        self._jwt: Optional[Tuple[float, str]] = None
        self._lock = threading.Lock()

    def _token(self) -> str:
        import jwt  # noqa: PLC0415
        with self._lock:
            now = time.time()
            if self._jwt is None or now - self._jwt[0] > 40 * 60:   # APNs wants a refresh between 20 and 60 minutes
                token = jwt.encode({"iss": self.team_id, "iat": int(now)}, self._key, algorithm="ES256",
                                   headers={"kid": self.key_id})
                self._jwt = (now, token)
            return self._jwt[1]

    def _client(self, environment: str) -> Any:
        with self._lock:
            if environment not in self._clients:
                self._clients[environment] = self._httpx.Client(base_url=APNS_HOSTS[environment], http2=True, timeout=10)
            return self._clients[environment]

    def __call__(self, device_token: str, device: Dict[str, Any], note: Dict[str, Any]) -> Tuple[int, str]:
        headers = {"authorization": "bearer " + self._token(), "apns-topic": self.topic,
                   "apns-push-type": note["push_type"], "apns-priority": str(note["priority"])}
        try:
            r = self._client(device.get("environment", "production")).post(
                "/3/device/" + device_token, headers=headers, content=json.dumps(note["payload"]))
        except Exception as e:  # network trouble: report, never crash the relay
            return 0, str(e)
        reason = ""
        if r.status_code != 200:
            try:
                reason = r.json().get("reason", "")
            except ValueError:
                reason = r.text
        return r.status_code, reason


# MARK: - Relay logic --------------------------------------------------------------------------------------------

def pick(payload: Dict[str, Any], *names: str) -> str:
    """First non-empty field among `names`, also trying the InfluxDB underscore-prefixed spelling."""
    for n in names:
        for key in (n, "_" + n):
            v = payload.get(key)
            if v not in (None, ""):
                return str(v)
    return ""


class Relay:
    def __init__(self, state: State, sender: Sender, secret: str, notify_ok: bool = True) -> None:
        self.state, self.sender, self.secret, self.notify_ok = state, sender, secret, notify_ok

    def authorized(self, header: str) -> bool:
        prefix = "bearer "
        given = header[len(prefix):] if header.lower().startswith(prefix) else header
        return bool(self.secret) and hmac.compare_digest(given.strip().encode(), self.secret.encode())

    # InfluxDB posts one JSON status object per notification.
    def handle_alert(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        check_id = pick(payload, "check_id", "check_name") or "unknown"
        name = pick(payload, "check_name", "notification_rule_name") or "InfluxDB alert"
        level = pick(payload, "level").lower() or "unknown"
        message = pick(payload, "message")
        with self.state.lock:
            previous = self.state.levels.get(check_id, {}).get("level")
            self.state.levels[check_id] = {"level": level, "name": name, "time": int(time.time())}
            if level not in ACTIVE_LEVELS and level != "ok":
                self.state.levels.pop(check_id, None)   # info / unknown: not tracked as an active alert
            self.state.save()
            badge = self.state.active_count()
        if previous == level:
            return {"sent": 0, "skipped": "level unchanged"}
        if level == "ok":
            if previous not in ACTIVE_LEVELS:
                return {"sent": 0, "skipped": "recovery without prior alert"}
            # recovery: silent, banner only if enabled; the badge always updates
            return self._push(name, "Back to normal", level, check_id, badge, silent=True, show_alert=self.notify_ok)
        if level not in ACTIVE_LEVELS:
            return {"sent": 0, "skipped": "level %s" % level}
        return self._push(name, message or level.upper(), level, check_id, badge, silent=False)

    def send_test(self) -> Dict[str, Any]:
        return self._push("InfluxOnTV", "Test notification: the push relay works.", "info", "test",
                          self.state.active_count(), silent=False)

    def _push(self, title: str, body: str, level: str, check_id: str, badge: int, silent: bool,
              show_alert: bool = True) -> Dict[str, Any]:
        sent = failed = 0
        with self.state.lock:
            devices = list(self.state.devices.items())
        for token, info in devices:
            if info.get("platform") == "tvos":
                # Apple TV only supports badges and silent updates: no alert text
                aps: Dict[str, Any] = {"badge": badge, "content-available": 1}
                note = {"push_type": "alert", "priority": 5}
            else:
                aps = {"badge": badge, "thread-id": check_id}
                if show_alert:
                    aps["alert"] = {"title": title, "body": body}
                if show_alert and not silent:
                    aps["sound"] = "default"
                note = {"push_type": "alert", "priority": 10}
            note["payload"] = {"aps": aps, "level": level, "check": title, "message": body}
            status, reason = self.sender(token, info, note)
            if status == 200:
                sent += 1
            else:
                failed += 1
                log.warning("APNs %s for %s (%s): %s", status, info.get("name", "?"), info.get("platform"), reason)
                if status == 410 or reason in ("BadDeviceToken", "Unregistered", "DeviceTokenNotForTopic"):
                    self.state.remove(token)
        log.info("alert %s -> %s: sent=%d failed=%d", title, level, sent, failed)
        return {"sent": sent, "failed": failed}


# MARK: - HTTP server --------------------------------------------------------------------------------------------

def make_handler(relay: Relay) -> type:
    class Handler(BaseHTTPRequestHandler):
        server_version = "InfluxOnTVPush/1.0"

        def log_message(self, fmt: str, *args: Any) -> None:
            log.debug("%s - %s", self.address_string(), fmt % args)

        def _reply(self, code: int, obj: Dict[str, Any]) -> None:
            data = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _body(self) -> Optional[Dict[str, Any]]:
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > 1_000_000:
                    return None
                data = json.loads(self.rfile.read(length) or b"{}")
                return data if isinstance(data, dict) else None
            except (ValueError, OSError):
                return None

        def do_GET(self) -> None:
            if self.path == "/health":
                self._reply(200, {"ok": True, "devices": len(relay.state.devices), "active": relay.state.active_count()})
            else:
                self._reply(404, {"error": "not found"})

        def do_POST(self) -> None:
            if not relay.authorized(self.headers.get("Authorization", "")):
                self._reply(401, {"error": "unauthorized"})
                return
            body = self._body()
            if body is None:
                self._reply(400, {"error": "invalid JSON body"})
                return
            if self.path == "/alert":
                self._reply(200, relay.handle_alert(body))
            elif self.path == "/register":
                token = str(body.get("token", ""))
                platform = body.get("platform", "ios")
                env = body.get("environment", "production")
                if not TOKEN_RE.match(token) or platform not in ("ios", "tvos") or env not in APNS_HOSTS:
                    self._reply(400, {"error": "invalid token, platform or environment"})
                    return
                relay.state.register(token, platform, env, str(body.get("name", ""))[:60])
                log.info("registered %s device %s (%s)", platform, body.get("name", "?"), env)
                self._reply(200, {"ok": True, "devices": len(relay.state.devices)})
            elif self.path == "/unregister":
                relay.state.remove(str(body.get("token", "")))
                self._reply(200, {"ok": True})
            elif self.path == "/test":
                self._reply(200, relay.send_test())
            else:
                self._reply(404, {"error": "not found"})

    return Handler


def load_config(path: str) -> Dict[str, Any]:
    with open(path) as f:
        cfg = json.load(f)
    for key in ("shared_secret", "apns_key_path", "apns_key_id", "apns_team_id"):
        if not cfg.get(key):
            raise SystemExit("config: missing '%s'" % key)
    return cfg


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default="config.json")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_config(args.config)
    sender = ApnsSender(cfg["apns_key_path"], cfg["apns_key_id"], cfg["apns_team_id"],
                        cfg.get("topic", "com.mfcorp.InfluxOnTV"))
    relay = Relay(State(cfg.get("state_path", "state.json")), sender, cfg["shared_secret"], cfg.get("notify_ok", True))
    srv = ThreadingHTTPServer((cfg.get("listen_host", "0.0.0.0"), int(cfg.get("listen_port", 8787))), make_handler(relay))
    log.info("listening on %s:%s", *srv.server_address[:2])
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
