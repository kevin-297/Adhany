# Adhany

Prayer times from your terminal. Adhan is split into two parts:

- **`adhand`**: a small daemon that calculates prayer times with [`adhanpy`](https://pypi.org/project/adhanpy/) and answers requests as JSON lines over a Unix socket.
- **`adhan`**: a thin command-line client (standard library only) that talks to the daemon and prints the results.

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

## Requirements

- Python 3.9 or newer (developed on 3.14)
- Linux with systemd (optional, for running the daemon as a user service)

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

Make sure `~/.local/bin` is in your `PATH`. The CLI uses `#!/usr/bin/env python3` and needs no virtual environment.

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

| Key          | Default      | Meaning                                                      |
|--------------|--------------|--------------------------------------------------------------|
| `latitude`   | `34.01325`   | Degrees, -90 to 90                                           |
| `longitude`  | `-6.83255`   | Degrees, -180 to 180                                         |
| `fajr_angle` | `19`         | Sun angle for Fajr, in degrees (0.01 to 30)                  |
| `isha_angle` | `17`         | Sun angle for Isha, in degrees (0.01 to 30)                  |
| `asr`        | `standard`   | Asr shadow rule: `standard` or `hanafi`                      |
| `adjustments`| `{}`         | Whole-minute shifts per prayer, e.g. `{"isha": 2}`           |
| `neighbors`  | `false`      | Default for including the previous Isha and next Fajr        |
| `socket`     | `$XDG_RUNTIME_DIR/adhand.sock` | Socket path (edit the file and restart to change) |

Notes:

- Times are calculated from the sun angles above. No preset method is used, so there are no hidden built-in adjustments.
- Adjustments merge with the saved ones. To remove one, set it to `0`, for example `adhan config set --adjust isha=0`.
- Valid adjustment names are `fajr`, `sunrise`, `dhuhr`, `asr`, `maghrib`, `isha`.
- The config file is validated on startup. Unknown keys or bad values make the daemon exit with a `bad config` message instead of running with wrong settings.

### Environment variables

| Variable          | Used by | Effect                                                         |
|-------------------|---------|----------------------------------------------------------------|
| `ADHAND_CONFIG`   | daemon  | Path to the config file (default `~/.config/adhand/config.json`) |
| `ADHAND_SOCKET`   | CLI     | Socket path to connect to                                      |
| `XDG_RUNTIME_DIR` | both    | Base directory for the default socket (falls back to `/tmp`)   |

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
```

Typical output (values are illustrative):

```
$ adhan
Thu 2026-10-01
  Fajr    05:42
  Sunrise 07:01
  Dhuhr   13:20
  Asr     16:38
  Maghrib 19:34
  Isha    20:55
Next: Asr 16:38 (in 2h 14m)

$ adhan now
Previous: Dhuhr 13:20 (1h 12m ago)
Next:     Asr 16:38 (in 2h 14m)
```

### Options

Every command accepts these:

| Option          | Meaning                                                              |
|-----------------|----------------------------------------------------------------------|
| `--socket PATH` | Daemon socket (default: `$ADHAND_SOCKET`, then `$XDG_RUNTIME_DIR/adhand.sock`) |
| `--json`        | Print JSON instead of text                                           |
| `--tz NAME`     | Show times in this IANA timezone, e.g. `Africa/Casablanca` (default: system timezone) |

Commands that calculate times (`today`, `date`, `next`, `previous`, `now`, `export`, `config set`) also accept the calculation settings:

| Option              | Meaning                                              |
|---------------------|------------------------------------------------------|
| `--lat DEG`         | Latitude                                             |
| `--lon DEG`         | Longitude                                            |
| `--fajr-angle DEG`  | Fajr sun angle                                       |
| `--isha-angle DEG`  | Isha sun angle                                       |
| `--asr RULE`        | `standard` or `hanafi`                               |
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

### Exit codes

| Code | Meaning                                       |
|------|-----------------------------------------------|
| `0`  | OK                                            |
| `1`  | Daemon error or usage error (including bad flags) |
| `2`  | Cannot reach the daemon                       |

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
- With `neighbors`, it also returns `previous_isha` and `next_fajr` (the previous day's Isha and the next day's Fajr), or `null` if one cannot be calculated.
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

**Daemon logs:**

```bash
journalctl --user -u adhand.service -f
```

**Updating the daemon:** copy the new `adhand.py` into `~/.local/share/adhand/`, then run `systemctl --user restart adhand.service`.

## License

See [LICENSE](LICENSE).
