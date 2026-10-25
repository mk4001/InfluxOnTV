# InfluxOnTV push relay

Sends **push notifications to iPad and Apple TV when an InfluxDB check changes level, even with the app closed.**

```
InfluxDB notification rule ──POST /alert──▶ relay (Raspberry) ──▶ Apple Push (APNs) ──▶ devices
InfluxOnTV app ───────────POST /register──▶ relay
```

* iPad: banner with the check name and message, sound, badge.
* Apple TV: Apple only allows the app-icon badge (number of active alerts) and silent wake-ups.
* Recoveries (`ok`) clear the badge silently. Repeated posts with the same level are ignored.

## 1. Apple side (once)

1. [developer.apple.com](https://developer.apple.com/account) → *Certificates, Identifiers & Profiles* → *Keys* → **+** → tick *Apple Push Notifications service (APNs)* → download `AuthKey_XXXXXXXXXX.p8` (it can only be downloaded once).
2. Note the **Key ID** (the `XXXXXXXXXX` part) and your **Team ID** (`9U36S4Q77X`).
3. Nothing else: the app's *Push Notifications* capability is already declared in its entitlements.

## 2. Raspberry

```bash
mkdir -p ~/influxontv-push && cd ~/influxontv-push
# copy influxontv_push.py, requirements.txt, config.example.json and influxontv-push.service here, plus the .p8 key
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
cp config.example.json config.json      # edit: shared_secret (long random string), apns_key_path, apns_key_id
chmod 600 config.json AuthKey_*.p8
sudo cp influxontv-push.service /etc/systemd/system/
sudo systemctl enable --now influxontv-push
curl http://localhost:8787/health       # → {"ok": true, ...}
```

Generate a secret with `openssl rand -hex 24`.

## 3. InfluxDB

In the InfluxDB UI (*Alerts*):

1. **Notification Endpoints → Create → HTTP**: URL `http://127.0.0.1:8787/alert`, method `POST`, authentication **Bearer** with the `shared_secret` as token.
2. **Notification Rules → Create**: every `1m`, *status changes from* **any** *to* **crit**, **warn** and **ok** (add one condition per level), endpoint = the one above.

## 4. Apps

On every device: *Settings → Push notifications*, enter `http://<raspberry>:8787` and the secret, then *Register this device*.
*Send test notification* checks the whole chain.

Debug builds register with Apple's **sandbox** push service, TestFlight/App Store builds with **production**; the relay handles both at once.

## Tests

```bash
python3 -m unittest -v test_relay     # no network, no Apple account needed
```

## Notes

* The relay talks HTTP on your LAN. Keep the port closed to the internet.
* Dead device tokens (app deleted) are removed automatically when APNs answers 410.
* `state.json` holds the registered device tokens and the last level of each check.
