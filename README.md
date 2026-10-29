# Adhany

Prayer times from your terminal and your status bar. Adhany is split into two parts:

- **`adhand`**: a small daemon that calculates prayer times with [`adhanpy`](https://pypi.org/project/adhanpy/) and answers requests as JSON lines over a Unix socket.
- **`adhan`**: a thin command-line client (standard library only) that talks to the daemon. It prints times and countdowns in the terminal, exports them to files, and provides a ready-made module for [Waybar](https://github.com/Alexays/Waybar).

The CLI does no calculation itself. Only the daemon needs `adhanpy`.

```
.
├── Adhand/
│   ├── adhand.py          # the daemon
│   └── requirements.txt   # daemon dependencies (adhanpy)
├── Adhan-cli/
│   └── adhany             # the CLI (installed as `adhan`)
└── LICENSE
```

## Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Waybar module](#waybar-module)
- [Scripting and the socket protocol](#scripting-and-the-socket-protocol)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Requirements

- Python 3.9 or newer (developed on 3.14)
- Linux with systemd (optional, for running the daemon as a user service)
- Waybar (optional, only for the [status bar module](#waybar-module)), plus `pkill` from `procps` for the click-to-flip feature
- A [Nerd Font](https://www.nerdfonts.com/) (optional, only if you use icons in the Waybar module)

## Installation

### 1. Install the daemon

The daemon lives in `~/.local/share/adhand/` with its own virtual environment:

```bash
mkdir -p ~/.local/share/adhand
cp Adhand/adhand.py Adhand/requirements.txt ~/.local/share/adhand/
python -m venv ~/.local/share/adhand/venv
~/.local/share/adhand/venv/bin/pip install -r ~/.local/share/adhand/requirements.txt
```

You never need to activate the venv. Services and scripts call its interpreter directly.

### 2. Run it as a systemd user service

Create `~/.config/systemd/user/adhand.service`:

```ini
[Unit]
Description=Adhan time calculator daemon

[Service]
ExecStart=%h/.local/share/adhand/venv/bin/python %h/.local/share/adhand/adhand.py
Restart=on-failure
RestartSec=2

[Install]
WantedBy=default.target
```

`%h` expands to your home directory. Enable and start it:

```bash
systemctl --user daemon-reload
systemctl --user enable --now adhand.service
systemctl --user status adhand.service
```

To keep the daemon running while you are logged out:

```bash
loginctl enable-linger $USER
```

On first start the daemon creates its config file with defaults and logs where it is listening:

```
adhand listening on /run/user/1000/adhand.sock (config: /home/you/.config/adhand/config.json)
```

### 3. Install the CLI

Symlink the script onto your `PATH` so edits take effect immediately:

```bash
chmod +x Adhan-cli/adhany
ln -sf "$(pwd)/Adhan-cli/adhany" ~/.local/bin/adhan
```

Or copy it instead:

```bash
install -m 755 Adhan-cli/adhany ~/.local/bin/adhan
```

Make sure `~/.local/bin` is in your `PATH`. The CLI uses `#!/usr/bin/env python3` and needs no virtual environment. The rest of this document refers to the installed name, `adhan`.

### Running without systemd

```bash
~/.local/share/adhand/venv/bin/python ~/.local/share/adhand/adhand.py
```

The daemon stops cleanly on `Ctrl+C` or `SIGTERM` and removes its socket.

## Configuration

**The default location is Rabat, Morocco. Set your own before relying on the times.**

```bash
adhan config set --lat 51.5072 --lon -0.1276   # your city
adhan config                                   # show the saved settings
```

Settings are saved in `~/.config/adhand/config.json` (written atomically) and survive restarts. Only the flags you pass are changed.

| Key           | Default                        | Meaning                                              |
|---------------|--------------------------------|------------------------------------------------------|
| `latitude`    | `34.01325`                     | Degrees, -90 to 90                                   |
| `longitude`   | `-6.83255`                     | Degrees, -180 to 180                                 |
| `fajr_angle`  | `19`                           | Sun angle for Fajr, in degrees (0.01 to 30)          |
| `isha_angle`  | `17`                           | Sun angle for Isha, in degrees (0.01 to 30)          |
| `asr`         | `standard`                     | Asr shadow rule: `standard` or `hanafi`              |
| `adjustments` | `{}`                           | Whole-minute shifts per prayer, e.g. `{"isha": 2}`   |
| `neighbors`   | `false`                        | Default for including the previous Isha and next Fajr |
| `socket`      | `$XDG_RUNTIME_DIR/adhand.sock` | Socket path (edit the file and restart to change)    |

Notes:

- Times are calculated from the sun angles above. No preset method is used, so there are no hidden built-in adjustments.
- Adjustments merge with the saved ones. To remove one, set it to `0`, for example `adhan config set --adjust isha=0`.
- Valid adjustment names are `fajr`, `sunrise`, `dhuhr`, `asr`, `maghrib`, `isha`.
- The config file is validated on startup. Unknown keys or bad values make the daemon exit with a `bad config` message instead of running with wrong settings.
- The [Waybar module](#waybar-module) always uses these saved settings.

### Environment variables

| Variable          | Used by | Effect                                                           |
|-------------------|---------|------------------------------------------------------------------|
| `ADHAND_CONFIG`   | daemon  | Path to the config file (default `~/.config/adhand/config.json`) |
| `ADHAND_SOCKET`   | CLI     | Socket path to connect to                                        |
| `XDG_RUNTIME_DIR` | both    | Base directory for the default socket and the Waybar flip state file (falls back to `/tmp`) |

To set `ADHAND_CONFIG` for the service, add `Environment=ADHAND_CONFIG=/path/to/config.json` to the `[Service]` section.

## Usage

```
adhan [-h] COMMAND ...
```

Running `adhan` with no command, or with only flags (such as `adhan --json`), means `adhan today`.

| Command    | Description                                                        |
|------------|--------------------------------------------------------------------|
| `today`    | Today's times and the next prayer (default command)                |
| `date`     | Times for one date                                                 |
| `next`     | The next prayer with a countdown                                   |
| `previous` | The previous prayer and how long ago it was                        |
| `now`      | Both the previous and the next prayer                              |
| `export`   | Export times for a year, a month, or a date range (up to 10 years) |
| `config`   | Show the daemon's saved settings (`config set` changes them)       |
| `waybar`   | Status bar module for Waybar: `show`, `flip`, `preview` (see [Waybar module](#waybar-module)) |
| `ping`     | Check that the daemon answers                                      |
| `raw`      | Send one raw JSON request and print the reply                      |

### Examples

```bash
adhan                                              # today's times and the next prayer
adhan now                                          # previous and next prayer with countdowns
adhan next --json                                  # machine-readable output for scripts
adhan date 2026-10-01                              # times for one day
adhan export --year 2026 --month 10                # one month as a table
adhan export --from 2026-10-01 --to 2026-10-20     # any date range (max 10 years)
adhan export --year 2026 --format csv -o 2026.csv  # a full year as CSV
adhan config set --lat 34.01 --lon -6.83           # change the daemon's saved settings
adhan waybar preview normal --at 2026-10-01T12:21:40   # see what the bar would show
```

Example output (default Rabat location):

```
$ adhan
Thursday 2026-10-29
  Fajr    06:15
  Sunrise 07:44
  Dhuhr   13:11
  Asr     16:13
  Maghrib 18:38
  Isha    19:57
Next: Maghrib 18:38 (in 35m)

$ adhan now
Previous: Asr 16:13 (1h 49m ago)
Next:     Maghrib 18:38 (in 35m)
```

### Options

Every command except the `waybar` subcommands accepts these:

| Option          | Meaning                                                              |
|-----------------|----------------------------------------------------------------------|
| `--socket PATH` | Daemon socket (default: `$ADHAND_SOCKET`, then `$XDG_RUNTIME_DIR/adhand.sock`) |
| `--json`        | Print JSON instead of text                                           |
| `--tz NAME`     | Show times in this IANA timezone, e.g. `Africa/Casablanca` (default: system timezone) |

Commands that calculate times (`today`, `date`, `next`, `previous`, `now`, `export`, `config set`) also accept the calculation settings:

| Option              | Meaning                                                     |
|---------------------|-------------------------------------------------------------|
| `--lat DEG`         | Latitude                                                    |
| `--lon DEG`         | Longitude                                                   |
| `--fajr-angle DEG`  | Fajr sun angle                                              |
| `--isha-angle DEG`  | Isha sun angle                                              |
| `--asr RULE`        | `standard` or `hanafi`                                      |
| `--adjust NAME=MIN` | Shift a prayer by whole minutes, e.g. `isha=2` (repeatable) |

On everything except `config set`, these flags are **one-off overrides**: they apply to that command only and nothing is saved. This is handy for checking another city or method:

```bash
adhan --lat 21.4225 --lon 39.8262 --tz Asia/Riyadh      # Mecca, without touching your config
adhan next --asr hanafi --adjust isha=2
```

`adhan config set` saves the same flags to the daemon, and also accepts `--neighbors true|false`.

`next`, `previous` and `now` also take `--with-sunrise`, which counts sunrise as a prayer time (off by default).

### Export

```
adhan export [--year Y] [--month 1-12] [--from DATE --to DATE]
             [--format table|csv|json|ics] [-o FILE]
```

- With no range options, it exports the current year. `--month` narrows it to one month.
- `--from` and `--to` (inclusive, `YYYY-MM-DD`) set a custom range and cannot be combined with `--year` or `--month`.
- The limit is 3660 days (about 10 years). For longer periods, run separate exports.
- Dates must fall between the years 1970 and 2100.
- `table` and `csv` have the columns Weekday, Day, Month, then the six times.
- `json` is the daemon's raw reply for each day, with Unix timestamps.
- `ics` produces a calendar file with the five prayers (sunrise is excluded), one event per prayer in UTC, ready to import into a calendar app.
- Without `-o`, output goes to the terminal, so you can pipe it, for example `adhan export --format csv | head`.
- If any day fails to calculate, nothing is written.

```
$ adhan export --from 2026-10-01 --to 2026-10-03
Weekday   Day  Month    Fajr   Sunrise  Dhuhr  Asr    Maghrib  Isha
Thursday    1  October  05:54  07:22    13:17  16:38  19:12    20:30
Friday      2  October  05:54  07:22    13:17  16:37  19:10    20:28
Saturday    3  October  05:55  07:23    13:16  16:36  19:09    20:27
```

### Exit codes

| Code | Meaning                                           |
|------|---------------------------------------------------|
| `0`  | OK                                                |
| `1`  | Daemon error or usage error (including bad flags) |
| `2`  | Cannot reach the daemon                           |

`adhan waybar show` is the exception: it always prints valid JSON and exits `0`, even when the daemon is down, so the bar never shows a traceback.

## Waybar module

Adhany includes a module for [Waybar](https://github.com/Alexays/Waybar) that puts the current prayer in your status bar. It is a Waybar `custom` module, so it works with any compositor Waybar supports (the example below is from a Hyprland setup).

The bar shows one prayer at a time, with a countdown when it is close:

```
 Dhuhr 13:17        the next prayer is more than an hour away
 Dhuhr -12 min      the next prayer is less than an hour away
 Dhuhr +28 min      the prayer began less than 30 minutes ago
```

- **Hover** over it for a tooltip with the full day, with the next prayer highlighted.
- **Click** it to see the other prayer for 10 seconds. Click again to cancel early.
- If the daemon is not reachable it shows `adhan offline` instead of failing, and recovers by itself once the daemon is back.

### Setup

Make sure the daemon is running and the CLI is installed as `~/.local/bin/adhan` (see [Installation](#installation)). Then add the module to your Waybar config (`~/.config/waybar/config.jsonc`) and place it in one of your `modules-*` lists:

```jsonc
"modules-center": ["custom/adhan"],

"custom/adhan": {
    "exec": "$HOME/.local/bin/adhan waybar show",
    "return-type": "json",
    "interval": 15,
    "signal": 8,
    "on-click": "$HOME/.local/bin/adhan waybar flip --signal 8",
    "format": "{icon}  {text}",
    "format-icons": {
        "fajr": "\ue34c",
        "dhuhr": "\ue30d",
        "asr": "\ue30c",
        "maghrib": "\ue34d",
        "isha": "\ue32b",
        "offline": "\uf071"
    },
    "min-length": 18,
    "align": 0.5
}
```

What each setting does:

| Setting | Why |
|---------|-----|
| `exec` | Runs `adhan waybar show`, which prints one JSON line. |
| `return-type: "json"` | Required, so Waybar reads `text`, `alt`, `class` and `tooltip` from that line. |
| `interval` | How often the bar refreshes, in seconds. The countdown has minute precision, so 15 is plenty. It also makes the bar pick up the next prayer and a restarted daemon on its own. |
| `signal` | The signal number that refreshes this module on demand. It must match `--signal` in `on-click`. |
| `on-click` | Runs `adhan waybar flip`. |
| `format` / `format-icons` | `{icon}` is chosen by the `alt` field, which is the lowercase prayer name (or `offline`). Drop `{icon}` and `format-icons` if you do not want icons. Sunrise is never shown on the bar, so it needs no icon. |
| `min-length: 18` | Reserves space for the longest text (`Maghrib -59 min`, plus icon and spacing) so the bar does not shift as the text changes. `align: 0.5` centers the text inside that space. |

Use the full path in `exec` and `on-click`, because Waybar may not have `~/.local/bin` on its `PATH`. `$HOME` is expanded by the shell Waybar runs commands in.

### Styling

The module sets one state class on the bar, so each state can have its own color:

```css
#custom-adhan { padding: 0 6px; }
#custom-adhan.next      { color: #89b4fa; }   /* next prayer is over an hour away */
#custom-adhan.countdown { color: #fab387; }   /* less than an hour to go          */
#custom-adhan.elapsed   { color: #a6e3a1; }   /* began less than 30 minutes ago   */
#custom-adhan.past      { color: #a6adc8; }   /* shown while flipped to the past  */
#custom-adhan.offline   { color: #6c7086; }   /* daemon not reachable             */
```

The module also adds a `flipped` class while a click is active, which you can style too, for example `#custom-adhan.flipped { font-style: italic; }`.

| Class       | When |
|-------------|------|
| `next`      | The shown prayer is more than 60 minutes away. Text: `Dhuhr 13:17` |
| `countdown` | The shown prayer is less than 60 minutes away. Text: `Dhuhr -12 min` |
| `elapsed`   | The shown prayer began less than 30 minutes ago. Text: `Dhuhr +28 min` |
| `past`      | The shown prayer began more than 30 minutes ago. This is what a click shows once the bar has moved on to the next prayer. Text: `Fajr 05:54` |
| `offline`   | The daemon is unreachable or returned an error. Text: `adhan offline` or `adhan error` |
| `flipped`   | Added on top of the classes above while a click is active. |

The tooltip is rendered with the `tooltip` selector in your Waybar CSS. Its columns are aligned with spaces, so it looks best in a monospace font.

### How the bar decides what to show

1. For 30 minutes after a prayer begins, the bar keeps showing it, counting up (`Dhuhr +05 min`).
2. After that it switches to the next prayer: a plain time first (`Asr 16:38`), then a countdown (`Asr -42 min`) for the last hour.
3. A click swaps the two: while the previous prayer is fresh it shows the next one, otherwise it shows the previous one. After 10 seconds (or a second click) it returns to normal.
4. Sunrise is not a prayer on the bar, so the sequence is Fajr, Dhuhr, Asr, Maghrib, Isha. After Isha it continues with tomorrow's Fajr, and before Fajr it still knows yesterday's Isha. Sunrise does appear in the tooltip.

Countdown minutes are rounded down and elapsed minutes up. The bar always uses the daemon's saved settings (see [Configuration](#configuration)), so change your location or method with `adhan config set`, not with flags on the module.

Real output for 1 October 2026, with the default Rabat location and `--tz Africa/Casablanca`:

| Time  | Normal view                 | After a click                     |
|-------|-----------------------------|-----------------------------------|
| 04:50 | `Fajr 05:54` (`next`)       | `Isha 20:31` (`past flipped`)     |
| 05:20 | `Fajr -34 min` (`countdown`) | `Isha 20:31` (`past flipped`)    |
| 08:00 | `Dhuhr 13:17` (`next`)      | `Fajr 05:54` (`past flipped`)     |
| 13:05 | `Dhuhr -12 min` (`countdown`) | `Fajr 05:54` (`past flipped`)   |
| 13:45 | `Dhuhr +28 min` (`elapsed`) | `Asr 16:38` (`next flipped`)      |
| 22:30 | `Fajr 05:54` (`next`)       | `Isha 20:30` (`past flipped`)     |

### Commands

```
adhan waybar show    [--socket PATH] [--tz NAME]
adhan waybar flip    [--signal N]
adhan waybar preview {normal,flipped,tooltip} [--at YYYY-MM-DDTHH:MM:SS] [--socket PATH] [--tz NAME]
```

| Command   | What it does |
|-----------|--------------|
| `show`    | Prints the module's JSON line. This is Waybar's `exec` command. |
| `flip`    | Starts (or cancels) a 10-second flip. This is Waybar's `on-click` command. `--signal N` is the module's Waybar signal number (default `8`) and must match `signal` in your Waybar config. |
| `preview` | Prints what the bar (`normal`, `flipped`) or the tooltip would show, as plain text, without touching any state. Use `--at` to pretend it is another local time (in `--tz` if given), which is the easiest way to check the edge cases above. |

`show` prints, for example:

```json
{"text": "Maghrib -35 min", "alt": "maghrib", "class": ["countdown"], "tooltip": "Thu 29 Oct 2026\nFajr     06:15\nSunrise  07:44\nDhuhr    13:11\nAsr      16:13\n<span foreground=\"#89b4fa\">Maghrib  18:38</span>\nIsha     19:57"}
```

And the same moment as a tooltip:

```
Thu 29 Oct 2026
Fajr     06:15
Sunrise  07:44
Dhuhr    13:11
Asr      16:13
Maghrib  18:38      <- highlighted
Isha     19:57
```

`preview` prints the bar text followed by the icon key and classes:

```
$ adhan waybar preview normal --at 2026-10-01T13:05:00 --tz Africa/Casablanca
Dhuhr -12 min    [icon: dhuhr, class: countdown]

$ adhan waybar preview flipped --at 2026-10-01T13:45:00 --tz Africa/Casablanca
Asr 16:38    [icon: asr, class: next flipped]
```

In a terminal, `preview tooltip` colors the highlighted row. When piped, the markup is stripped.

### Customizing

The behavior is controlled by four constants at the top of the waybar section in `Adhan-cli/adhany`:

| Constant           | Default   | Meaning |
|--------------------|-----------|---------|
| `ELAPSED_WINDOW`   | `30 * 60` | How long (seconds) the bar keeps showing a prayer after it begins. |
| `COUNTDOWN_WINDOW` | `60 * 60` | How long (seconds) before a prayer the bar switches to a countdown. |
| `FLIP_SECONDS`     | `10`      | How long a click shows the other prayer. |
| `HIGHLIGHT`        | `#89b4fa` | Tooltip color of the next prayer's row. |

If you installed the CLI by symlink, edits take effect immediately.

### How click-to-flip works

`flip` writes the time the flip should end into `$XDG_RUNTIME_DIR/adhan-waybar-flip` (or `/tmp/adhan-waybar-flip` if `XDG_RUNTIME_DIR` is unset). `show` reads that file on every run, so nothing is kept in memory. Waybar refreshes the module right after the click. Because Waybar would otherwise keep showing the flipped prayer until the next `interval`, `flip` also starts a small detached background job that sleeps until the flip ends and then runs `pkill -RTMIN+N waybar`. That wakes the module (signal number `N`, from `--signal`) so it switches back on time.

### Waybar troubleshooting

**The bar says `adhan offline`:** the daemon is not running or the module cannot find its socket. Run `adhan ping` in a terminal. If that works but the bar still says offline, Waybar is probably running without your `XDG_RUNTIME_DIR` or `ADHAND_SOCKET`. Check that `systemctl --user status adhand.service` is active, and make sure Waybar is started from your graphical session. The message in the tooltip tells you which socket path it tried.

**The bar says `adhan error`:** the daemon answered with an error. Hover over the module to read it, and see the [Troubleshooting](#troubleshooting) section.

**The bar does not go back after a click:** the signal numbers do not match. `"signal"` in the module and `--signal` in `on-click` must be the same number, and `pkill` must be installed. The module will still return to normal at its next `interval` refresh.

**Nothing happens on click:** run `adhan waybar flip` in a terminal and check for an error. It exits with code `1` if it cannot write the state file.

**Icons show as empty boxes:** your Waybar font does not include the glyphs. Set a Nerd Font in your Waybar CSS (for example `font-family: "JetBrainsMono Nerd Font"`), or remove `{icon}` from `format`.

**To check the module without waiting for the right time of day:** use `adhan waybar preview normal --at ...` as shown above.

## Scripting and the socket protocol

The daemon speaks one JSON object per line over a Unix socket. The socket is created owner-only (`0600`), so only your user can talk to it. For scripts, `adhan next --json` is usually enough:

```json
{"next":{"name":"asr","unix":1790872680}}
```

You can also talk to the socket directly, with `adhan raw` or any tool that can open a Unix socket:

```bash
adhan raw '{"method":"ping"}'
echo '{"method":"ping"}' | socat - UNIX-CONNECT:"$XDG_RUNTIME_DIR/adhand.sock"
```

### Requests

| Method       | Fields                                          | Result                                  |
|--------------|-------------------------------------------------|-----------------------------------------|
| `ping`       |                                                 | `"pong"`                                |
| `times`      | `date` (`YYYY-MM-DD`), optional `neighbors` (bool), optional `overrides` (object) | `{"date": ..., "times": {...}}` |
| `config.get` |                                                 | The current settings                    |
| `config.set` | `values` (object of settings to change)         | The new settings                        |

- `times` returns Unix timestamps for `fajr`, `sunrise`, `dhuhr`, `asr`, `maghrib` and `isha`.
- With `neighbors`, it also returns `previous_isha` and `next_fajr` (the previous day's Isha and the next day's Fajr), or `null` if one cannot be calculated. The Waybar module always asks for these.
- `overrides` accepts the calculation settings from the config table (everything except `socket` and `neighbors`) for that request only.
- Any request may carry an `id`, which is echoed in the reply. Requests can be pipelined on one connection, and replies come back in order.

```json
{"id": 1, "method": "times", "date": "2026-10-01", "neighbors": true, "overrides": {"asr": "hanafi"}}
{"id": 2, "method": "config.set", "values": {"fajr_angle": 18.5, "adjustments": {"isha": 2}}}
```

### Replies

Success: `{"ok": true, "result": ...}`. Failure: `{"ok": false, "error": "code", "message": "..."}`.

| Error            | Meaning                                                      |
|------------------|--------------------------------------------------------------|
| `invalid_json`   | The line is not valid JSON, or not a JSON object             |
| `invalid_param`  | A field is missing, has the wrong type or is out of range, or the key is unknown |
| `unknown_method` | The `method` is not one of the above                         |
| `calc_failed`    | Times cannot be calculated for that date and location (for example, extreme latitudes) |
| `internal`       | Unexpected error; the details are in the daemon's log        |

## Troubleshooting

**Exit code 2 / "cannot connect":** check that the service is running and the socket exists.

```bash
adhan ping
systemctl --user status adhand.service
ls -l "$XDG_RUNTIME_DIR/adhand.sock"
```

**"adhand is already running":** another daemon is answering on that socket. A leftover socket from a crash is detected and removed automatically.

**"bad config ...":** the daemon refused to start because of an invalid value in the config file. Fix it, or delete the file to regenerate the defaults.

**Times look wrong:** check your location with `adhan config`, and remember the default is Rabat. Also compare the angles and Asr rule against the method your local mosque uses.

**Problems with the status bar:** see [Waybar troubleshooting](#waybar-troubleshooting).

**Daemon logs:**

```bash
journalctl --user -u adhand.service -f
```

**Updating the daemon:** copy the new `adhand.py` into `~/.local/share/adhand/`, then run `systemctl --user restart adhand.service`. The CLI, including the Waybar module, needs no restart if you installed it by symlink. Waybar picks up changes to `adhan` the next time it runs the command.

## License

Adhany is licensed under the GNU Affero General Public License v3.0. See [LICENSE](LICENSE).
