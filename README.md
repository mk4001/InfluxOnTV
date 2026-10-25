# InfluxOnTV

Your InfluxDB 2.x dashboards, on the Apple TV and the iPad.

**InfluxOnTV** reads the dashboards you already designed in InfluxDB (charts, gauges, single values, tables, notes) and shows them full screen, always up to date, with no cloud service and no registration: the app talks directly to your own InfluxDB server. It is made for a screen that stays on: automatic rotation between dashboards, alerts from your InfluxDB checks, a server health page, a night mode, and a built-in demo that needs no server at all.

| | |
|---|---|
| Support | <https://www.mf-lab.com/support/> |
| Privacy policy | <https://mf-lab.com/privacy> (also inside the app: *About → Privacy Policy*) |

## Contents

- [What it does](#what-it-does)
- [Requirements](#requirements)
- [Quick start](#quick-start)
- [Try it without a server](#try-it-without-a-server)
- [Using the app](#using-the-app)
- [Alerts and push notifications](#alerts-and-push-notifications)
- [Widgets and Top Shelf](#widgets-and-top-shelf)
- [Several servers and iCloud](#several-servers-and-icloud)
- [Troubleshooting](#troubleshooting)
- [Privacy](#privacy)
- [Credits](#credits)

## What it does

- **Every dashboard you already have:** line, step, bar and stacked-area charts, band, scatter, histogram, heatmap and mosaic, single-stat, line-plus-single-stat, gauge, tables and markdown notes. Dashboard variables (query, map, constant) and the time range selector (15 minutes to 90 days, today, yesterday, or a custom range on iPad) work as in InfluxDB.
- **Made for a wall screen:** automatic rotation with a playlist (which dashboards, in which order, for how long) and schedule rules (pause, or keep one dashboard on screen, at certain days and hours); night mode that dims the picture and slows the refresh; pixel shift against burn-in on OLED and plasma TVs.
- **Alerts:** a banner and a sound when an InfluxDB check turns warning or critical, a bell that stays lit while alerts are active, the history, the state of your monitoring tasks and notification rules, and the thresholds of your checks drawn on the charts.
- **Server status:** version, uptime, memory, disk used by each bucket, queries and task runs, with problems flagged in plain words.
- **Zoom:** enlarge any cell, move a cursor along the chart to read every series, see last / minimum / maximum / average, and compare with the previous period.
- **Still useful when the server is not:** the last data is kept on the device, cells show how old their latest point is, and a red strip appears when the server does not answer (the app keeps retrying by itself).
- **Apple ecosystem:** iPad widgets, Apple TV Top Shelf, optional push notifications, credentials shared between your devices through your private iCloud.
- **Read-only:** the app only reads. A read-only API token is enough.

## Requirements

| Who | What |
|---|---|
| Apple TV | Apple TV running tvOS 17 or later. |
| iPad | iPadOS 17 or later (iPhone is not supported). |
| Server | InfluxDB **2.x** (open source or a server you host), reachable from the device: same network, VPN, or HTTPS on the internet. InfluxDB Cloud and InfluxDB 1.x are not supported yet. |
| Token | A read-only API token (see below). |

## Quick start

1. **Create a read-only token** in InfluxDB: *Load Data → API Tokens → Generate API Token → Custom*, with read access to **Buckets, Dashboards, Orgs and Variables**. To also see checks, notification rules, tasks and alerts, add read access to **Checks, Notification Rules, Tasks** and the **`_monitoring`** bucket. From a terminal:

   ```bash
   influx auth create --org <organization> \
     --read-buckets --read-dashboards --read-orgs \
     --read-checks --read-notificationRules --read-tasks
   ```

2. **Open InfluxOnTV → Settings** and enter the server URL (for example `http://192.168.1.20:8086`), the organization **name** (not its ID) and the token.
3. Choose **Test connection**: you should see the InfluxDB version and the number of dashboards.
4. Pick a dashboard. The next time the app opens it resumes from the last one you viewed.

If you use the iPad too, sign in to iCloud on both and the second device picks the credentials up by itself (see [Several servers and iCloud](#several-servers-and-icloud)).

## Try it without a server

*Settings → Demo → Try the demo (no server needed)* shows six synthetic dashboards, active alerts, monitoring tasks and server status, all generated on the device. Nothing is sent anywhere. A **guided tour** starts the first time (and can be replayed from *Settings → Demo → Guided tour*): captions over the real screens walk you through the main features. *Exit demo* in the same place brings back your own connection.

## Using the app

**Apple TV remote**

| Gesture | What it does |
|---|---|
| Swipe left / right on a dashboard | Previous / next dashboard |
| Up / down | Scroll a dashboard taller than the screen |
| Select | Quick menu: zoom into a cell, refresh now, pause the rotation, alerts |
| Press and hold Select on a card | Add or remove from favourites |
| In a zoomed cell: left / right | Move the cursor along the chart |
| Play/Pause | Pause or resume the rotation |
| Menu | Go back |

**iPad:** tap a dashboard to open it; tap a cell (or press and hold) to zoom; touch the chart to read values; tap the "rotation" label to pause the rotation.

**Main screen.** A row of icons is always one move away: **Alerts**, **Rotation** (default time per dashboard, data refresh, playlist and schedule rules), **Server**, **Settings**, **Help**, **About**. Under it your dashboards appear as cards with a small preview: *Favourites*, *Recent*, then *All dashboards*, grouped by the part of the name before " - " or ": " (for example "NAS - SNMP" and "NAS - UPS" go under "NAS").

**Rotation, in one place.** *Rotation → Timing* sets the default time each dashboard stays on screen (or Off) and how often data is read from the server. The playlist can give a different time to single dashboards, and the schedule rules win over both. Night mode (*Settings → Screen*) dims the screen, refreshes every 5 minutes and stops the rotation; a touch brings the picture back for a minute.

**Supported cells:** xy, band, scatter, histogram, heatmap, mosaic, single-stat, line-plus-single-stat, gauge, table, markdown. *Not supported yet:* check, geo and log-viewer (they show a notice; the other cells keep working).

## Alerts and push notifications

The app polls the `_monitoring` bucket of your server. A check that goes to warning or critical shows a banner for 15 seconds (with the sound chosen in *Settings → Display*), then only the bell stays lit. "No data" from a check is listed but is not treated as an active alert. A failed or stopped monitoring task counts as an alert; one you disabled does not.

To get alerts **with the app closed**, InfluxDB cannot talk to Apple's push service by itself, so a small relay runs next to it. It is a single Python file with a five-minute setup: see [`server/README.md`](server/README.md). On the iPad you get a banner and a sound; the Apple TV only shows the number of active alerts as a badge on the icon (an Apple limitation). Turn it on in *Settings → Push notifications*.

## Widgets and Top Shelf

- **iPad widgets:** *Alerts* (number of active alerts and the most urgent ones, also for the Lock Screen) and *Dashboard* (the main value or trend of the dashboard you pick: touch and hold the widget, *Edit Widget*). They refresh about every 15 minutes, as the system allows.
- **Apple TV Top Shelf:** with the app in the top row of the Home screen, the area above it shows the active alerts and your favourite dashboards with their latest value. Select one to open it.

Open the app once after setting up the connection, so the widgets and the Top Shelf know your server.

## Several servers and iCloud

*Settings → Saved connections* keeps more than one server or organization (home and office, say). The one with the check mark is in use; with two or more, the main screen gets a **Connection** row to switch quickly. Each connection has its own token in the system Keychain.

With *Sync with iCloud* on (the default), the URL, organization and token of the active connection are saved in your **private** CloudKit database (the token is an encrypted field) so your other devices pick them up. Use the same Apple ID on all of them. *Restore from iCloud* forces it. The demo connection is never sent to iCloud.

## Troubleshooting

| Symptom | What to check |
|---|---|
| **HTTP 401 "unauthorized"** | The token is wrong, expired or lacks read permissions. Create a new one (see [Quick start](#quick-start)). Use the organization **name**, not the ID. |
| **Cannot connect** | The device must be on the same network as the server (or reach it through a VPN). Allow the app to use the **Local Network** (system Settings → Privacy → Local Network). If a `.local` name does not resolve, use the IP address. Plain `http://` is allowed only on the local network; use `https://` for a server on the internet. |
| Red **"Server unreachable"** strip | The server did not answer for 5 seconds. The app keeps the last data and retries every 5 to 60 seconds until it is back. |
| Orange **"… ago"** badge on a cell | The latest point is older than expected (three times the usual interval, at least five minutes); the cell is dimmed. A *cached* tag means the values come from the copy saved on the device. |
| **"No data"** in a cell | The query returns nothing for the selected range: try a longer one. |
| Cell with an **orange notice** | It uses a property the app cannot read yet (check, geo, log-viewer); the other cells keep working. |
| No alerts, no bell | The token cannot read the `_monitoring` bucket and Checks: add those permissions. |
| "Task" or "Notification" lists are empty | Add read access to Tasks and Notification Rules. The address of a notification endpoint (for example a Slack webhook) is never read or shown. |
| **Dashboards do not rotate** | Rotation is *Off*, paused with Play/Pause, held by a schedule rule, or night mode is active. Check *Rotation → Timing* and the rules. |
| The second device does not get the credentials | Same Apple ID, signed in to iCloud, *Sync with iCloud* on; try *Restore from iCloud*. CloudKit can take a few minutes the first time. |
| Widgets or Top Shelf say "Open InfluxOnTV once" | Open the app with a working connection once. The Top Shelf only appears when the app is in the top row of the Home screen. |
| Push notifications do not arrive | *Settings → Push notifications → Send test notification*. The relay must be running and reachable from the device, and the shared secret must match. See [`server/README.md`](server/README.md). |
| Screen too dark at night | *Settings → Screen → Night mode*: set the hours and the dimming, or turn it off. |
| Image retention on an OLED or plasma TV | Turn on *Pixel shift* in *Settings → Screen*. |

When asking for support, please include: the app version (*About*), the device and tvOS / iPadOS version, the InfluxDB version (*Server* screen) and what you see on screen. **Never send your API token.**

## Privacy

InfluxOnTV does not collect, store or share personal data on any server operated by MF-Lab.com. It only talks to the InfluxDB server you configure and, if you leave *Sync with iCloud* on, to your own private iCloud account. If you turn on push notifications it also talks to the relay you host yourself and, through it, to Apple's push service. No analytics, no tracking, no advertising, no third-party SDKs. The full policy is in the app (*About → Privacy Policy*) and at <https://mf-lab.com/privacy>.

## Credits

InfluxOnTV is an independent app by MF-Lab. InfluxDB is a registered trademark of InfluxData Inc.; this project is not affiliated with or endorsed by InfluxData Inc. Apple, Apple TV, iPad, iCloud and CloudKit are trademarks of Apple Inc.

© 2026 MF-Lab.com
