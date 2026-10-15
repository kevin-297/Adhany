#!/usr/bin/env python3
"""adhand - tiny adhan time calculator daemon. JSON lines over a Unix socket.

Requests (one JSON object per line):
  {"method": "ping"}
  {"method": "times", "date": "2026-10-01", "neighbors": true, "overrides": {...}}
  {"method": "config.get"}
  {"method": "config.set", "values": {"fajr_angle": 18.5, "adjustments": {"isha": 2}}}
Any request may carry an "id"; it is echoed in the reply.
"""
import asyncio, json, os, re, signal, sys, traceback
from datetime import date, datetime, timedelta
from pathlib import Path

from adhanpy.PrayerTimes import PrayerTimes
from adhanpy.calculation.CalculationParameters import CalculationParameters
from adhanpy.calculation.Madhab import Madhab
from adhanpy.calculation.PrayerAdjustments import PrayerAdjustments

PRAYERS = ("fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha")
CONFIG_PATH = Path(os.environ.get("ADHAND_CONFIG", "~/.config/adhand/config.json")).expanduser()
RUNTIME = os.environ.get("XDG_RUNTIME_DIR", "/tmp")

# Rabat is only a starting point: set your own city with config.set.
DEFAULTS = {"socket": f"{RUNTIME}/adhand.sock", "neighbors": False,
            "latitude": 34.01325, "longitude": -6.83255,
            "fajr_angle": 19, "isha_angle": 17, "asr": "standard", "adjustments": {}}
EDITABLE = set(DEFAULTS) - {"socket"}      # what config.set may change
OVERRIDABLE = EDITABLE - {"neighbors"}     # what a "times" request may override


class Err(Exception):
    def __init__(self, code, msg):
        self.code, self.msg = code, msg


def num(v, lo, hi, name):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
        raise Err("invalid_param", f"{name} must be a number between {lo} and {hi}")


def check(values, allowed):
    """Validate settings; unknown keys are rejected so typos don't pass silently."""
    if not isinstance(values, dict):
        raise Err("invalid_param", "expected a JSON object")
    for k, v in values.items():
        if k not in allowed:
            raise Err("invalid_param", f"unknown key: {k}")
        if k == "latitude": num(v, -90, 90, k)
        elif k == "longitude": num(v, -180, 180, k)
        elif k in ("fajr_angle", "isha_angle"): num(v, 0.01, 30, k)
        elif k == "asr" and v not in ("standard", "hanafi"):
            raise Err("invalid_param", "asr must be 'standard' or 'hanafi'")
        elif k == "neighbors" and not isinstance(v, bool):
            raise Err("invalid_param", "neighbors must be true or false")
        elif k == "socket" and not isinstance(v, str):
            raise Err("invalid_param", "socket must be a string")
        elif k == "adjustments":
            if not isinstance(v, dict) or any(a not in PRAYERS or isinstance(m, bool)
                                              or not isinstance(m, int) for a, m in v.items()):
                raise Err("invalid_param", f"adjustments: integer minutes for {', '.join(PRAYERS)}")


def merge(base, new):
    out = {**base, **new}
    out["adjustments"] = {**base["adjustments"], **new.get("adjustments", {})}
    return out


def load_config():
    if not CONFIG_PATH.exists():
        save_config(DEFAULTS)
        return dict(DEFAULTS)
    saved = json.loads(CONFIG_PATH.read_text())
    try:
        check(saved, EDITABLE | {"socket"})
    except Err as e:
        sys.exit(f"bad config {CONFIG_PATH}: {e.msg}")
    return merge(DEFAULTS, saved)


def save_config(cfg):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2))
    os.replace(tmp, CONFIG_PATH)           # atomic: never leaves a half-written file


def calc_day(day, cfg):
    p = CalculationParameters()            # no preset, so no hidden built-in adjustments
    p.fajr_angle, p.isha_angle = cfg["fajr_angle"], cfg["isha_angle"]
    p.madhab = Madhab.HANAFI if cfg["asr"] == "hanafi" else Madhab.SHAFI
    p.adjustments = PrayerAdjustments(**cfg["adjustments"])
    try:
        pt = PrayerTimes((cfg["latitude"], cfg["longitude"]),
                         datetime(day.year, day.month, day.day), calculation_parameters=p)
    except RuntimeError:                   # adhanpy raises this when a time can't be solved
        raise Err("calc_failed", f"cannot calculate times for {day}")
    return {n: int(getattr(pt, n).timestamp()) for n in PRAYERS}


def parse_date(s):
    if not isinstance(s, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        raise Err("invalid_param", "date must be YYYY-MM-DD")
    try:
        d = date.fromisoformat(s)
    except ValueError:
        raise Err("invalid_param", "not a real date")
    if not 1970 <= d.year <= 2100:
        raise Err("invalid_param", "year must be 1970..2100")
    return d


def handle(req, state):
    if not isinstance(req, dict):
        raise Err("invalid_json", "request must be a JSON object")
    method = req.get("method")
    if method == "ping":
        return "pong"
    if method == "config.get":
        return state["cfg"]
    if method == "config.set":
        values = req.get("values")
        check(values, EDITABLE)
        new = merge(state["cfg"], values)
        save_config(new)                   # save first; memory changes only if saving worked
        state["cfg"] = new
        return new
    if method == "times":
        day = parse_date(req.get("date"))
        overrides = req.get("overrides", {})
        check(overrides, OVERRIDABLE)
        cfg = merge(state["cfg"], overrides)
        neighbors = req.get("neighbors", cfg["neighbors"])
        check({"neighbors": neighbors}, EDITABLE)
        result = {"date": day.isoformat(), "times": calc_day(day, cfg)}
        if neighbors:
            for key, d, prayer in (("previous_isha", day - timedelta(days=1), "isha"),
                                   ("next_fajr", day + timedelta(days=1), "fajr")):
                try:
                    result[key] = calc_day(d, cfg)[prayer]
                except Err:
                    result[key] = None
        return result
    raise Err("unknown_method", f"unknown method: {method!r}")


async def client(reader, writer, state):
    try:
        while line := await reader.readline():
            req_id = None
            try:
                try:
                    req = json.loads(line)
                except ValueError:
                    raise Err("invalid_json", "not valid JSON")
                if isinstance(req, dict):
                    req_id = req.get("id")
                resp = {"ok": True, "result": handle(req, state)}
            except Err as e:
                resp = {"ok": False, "error": e.code, "message": e.msg}
            except Exception:
                traceback.print_exc()
                resp = {"ok": False, "error": "internal", "message": "internal error"}
            if req_id is not None:
                resp = {"id": req_id, **resp}
            writer.write((json.dumps(resp, separators=(",", ":")) + "\n").encode())
            await writer.drain()
    except (ConnectionError, ValueError):  # client left, or sent an over-long line
        pass
    finally:
        writer.close()


async def main():
    state = {"cfg": load_config()}
    path = state["cfg"]["socket"]
    if os.path.exists(path):               # refuse if alive, remove if stale
        try:
            _, w = await asyncio.open_unix_connection(path)
            w.close()
            sys.exit("adhand is already running")
        except (ConnectionRefusedError, FileNotFoundError):
            os.unlink(path)
    old = os.umask(0o177)                  # socket is owner-only from the start
    server = await asyncio.start_unix_server(lambda r, w: client(r, w, state), path=path, limit=65536)
    os.umask(old)
    stop = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_running_loop().add_signal_handler(sig, stop.set)
    print(f"adhand listening on {path} (config: {CONFIG_PATH})", file=sys.stderr)
    await stop.wait()
    server.close()
    os.unlink(path)


if __name__ == "__main__":
    asyncio.run(main())
