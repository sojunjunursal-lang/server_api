import time
import random
import datetime
import socket
import struct
import zlib
import threading
import re
import json
import os

import zstandard as zstd
from Crypto.Cipher import AES
from enum import Enum
from typing import Any, Tuple, Optional, Dict, List
from collections import defaultdict
import sys as _sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in _sys.path:
    _sys.path.insert(0, _HERE)
from sdp import SdpStruct, SdpDataType, SdpException

HERO_ID_MAP = {
    1: "Miya", 2: "Balmond", 3: "Saber", 4: "Alice", 5: "Nana", 6: "Tigreal",
    7: "Alucard", 8: "Karina", 9: "Akai", 10: "Franco", 11: "Bane", 12: "Bruno",
    13: "Clint", 14: "Rafaela", 15: "Eudora", 16: "Zilong", 17: "Fanny", 18: "Layla",
    19: "Minotaur", 20: "Lolita", 21: "Hayabusa", 22: "Freya", 23: "Gord", 24: "Natalia",
    25: "Kagura", 26: "Chou", 27: "Sun", 28: "Alpha", 29: "Ruby", 30: "Yi Sun-shin",
    31: "Moskov", 32: "Johnson", 33: "Cyclops", 34: "Estes", 35: "Hilda", 36: "Aurora",
    37: "Lapu-Lapu", 38: "Vexana", 39: "Roger", 40: "Karrie", 41: "Gatotkaca", 42: "Harley",
    43: "Irithel", 44: "Grock", 45: "Argus", 46: "Odette", 47: "Lancelot", 48: "Diggie",
    49: "Hylos", 50: "Zhask", 51: "Helcurt", 52: "Pharsa", 53: "Lesley", 54: "Jawhead",
    55: "Angela", 56: "Gusion", 57: "Valir", 58: "Martis", 59: "Uranus", 60: "Hanabi",
    61: "Chang'e", 62: "Kaja", 63: "Selena", 64: "Aldous", 65: "Claude", 66: "Vale",
    67: "Leomord", 68: "Lunox", 69: "Hanzo", 70: "Belerick", 71: "Kimmy", 72: "Thamuz",
    73: "Harith", 74: "Minsitthar", 75: "Kadita", 76: "Faramis", 77: "Badang", 78: "Khufra",
    79: "Granger", 80: "Guinevere", 81: "Esmeralda", 82: "Terizla", 83: "X.Borg", 84: "Ling",
    85: "Dyrroth", 86: "Lylia", 87: "Baxia", 88: "Masha", 89: "Wanwan", 90: "Silvanna",
    91: "Cecilion", 92: "Carmilla", 93: "Atlas", 94: "Popol and Kupa", 95: "Yu Zhong",
    96: "Luo Yi", 97: "Benedetta", 98: "Khaleed", 99: "Barats", 100: "Brody", 101: "Yve",
    102: "Mathilda", 103: "Paquito", 104: "Gloo", 105: "Beatrix", 106: "Phoveus",
    107: "Natan", 108: "Aulus", 109: "Aamon", 110: "Valentina", 111: "Edith", 112: "Floryn",
    113: "Yin", 114: "Melissa", 115: "Xavier", 116: "Julian", 117: "Fredrinn", 118: "Joy",
    119: "Novaria", 120: "Arlott", 121: "Ixia", 122: "Nolan", 123: "Cici", 124: "Chip",
    125: "Zhuxin", 126: "Suyou", 127: "Lukas", 128: "Kalea", 129: "Zetian", 130: "Obsidia"
}

DEVICE_MODELS = [
    'Xiaomi:23049PCD8G', 'Xiaomi:2201123G', 'Xiaomi:22011211C', 'Xiaomi:2211133C',
    'Xiaomi:23078PND5G', 'Xiaomi:22101316G', 'Xiaomi:Redmi Note 12', 'Xiaomi:Redmi Note 12 Pro',
    'Xiaomi:Redmi Note 11', 'Xiaomi:Redmi 12C', 'Xiaomi:Redmi 10', 'Xiaomi:Mi 11',
    'Xiaomi:Mi 11 Ultra', 'Xiaomi:23013RK75G', 'Xiaomi:2304FPN6DG', 'Xiaomi:23054RA19I',
    'Xiaomi:22071219CG', 'Xiaomi:2206123SC', 'Xiaomi:220733SG', 'Xiaomi:22041219NY',
    'Xiaomi:2203121C', 'Xiaomi:2201116SG', 'Xiaomi:220333QNY', 'Xiaomi:22101316C',
    'Xiaomi:2210132C', 'Xiaomi:220733SPG', 'Xiaomi:2211133G', 'Xiaomi:2304FPN6DC',
    'Xiaomi:23090RA98C', 'Xiaomi:23106RN0DA', 'Xiaomi:2312DRA50C', 'Xiaomi:2201123C',
    'Xiaomi:2211101C', 'Xiaomi:2304FPN6DI', 'Xiaomi:2207117BPG', 'Xiaomi:2112123AC',
    'Xiaomi:22120RN86G', 'Xiaomi:2206122SC', 'Xiaomi:22041216I', 'Xiaomi:2207117BPI',
    'Xiaomi:Redmi Note 13', 'Xiaomi:Redmi Note 13 Pro', 'Xiaomi:Redmi 13C', 'Xiaomi:Redmi A3',
    'Xiaomi:POCO X6', 'Xiaomi:POCO M6', 'Xiaomi:POCO C65', 'Xiaomi:POCO F6',
    'Xiaomi:Mi 14', 'Xiaomi:Mi 14 Ultra',
]

AES_KEY = bytes.fromhex('f5a193d50ade553e9835595f5cd75ddd')
AES_IV = b'\x00' * 16

SKIN_TIER_LABELS = {
    'common': 'Common',
    'exceptional': 'Exceptional',
    'deluxe': 'Deluxe',
    'exquisite': 'Exquisite',
    'grand': 'Grand',
    'supreme': 'Supreme',
    'unknown': 'Unknown',
}

_SKIN_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'skin_db.json')
try:
    with open(_SKIN_DB_PATH, 'r', encoding='utf-8') as _f:
        _raw = _f.read().strip()
        if not _raw.startswith('{'):
            _raw = '{' + _raw
        SKIN_DB = json.loads(_raw)
except Exception:
    SKIN_DB = {}


def get_skin_tier(skin_id):
    tier = SKIN_DB.get(str(skin_id))
    if not tier:
        return None
    return SKIN_TIER_LABELS.get(tier, tier.capitalize())


def get_hero_history(tag_91: list) -> List[str]:
    hero_list = [HERO_ID_MAP.get(hid, f"Unknown({hid})") for hid in reversed(tag_91)]
    return hero_list[:5]


def map_collector_point(point: int) -> str:
    if point < 1000:
        return "No Tier"
    tiers = [
        (1000, 4000, "Amateur Collector"),
        (4000, 10000, "Junior Collector"),
        (10000, 22000, "Seasoned Collector"),
        (22000, 44000, "Expert Collector"),
        (44000, 84000, "Renowned Collector"),
        (84000, 160000, "Exalted Collector"),
        (160000, 280000, "Mega Collector"),
        (280000, float('inf'), "World Collector"),
    ]
    for min_p, max_p, name in tiers:
        if min_p <= point < max_p:
            if name == "World Collector":
                return "World Collector"
            per_level = (max_p - min_p) / 5
            level = int((point - min_p) // per_level)
            roman = ["V", "IV", "III", "II", "I"][level]
            return f"{name} {roman}"
    return "Unknown"


def parse_skin_counts(tag_118) -> dict:
    if not tag_118 or not isinstance(tag_118, dict):
        return {}

    skin_data = None
    for k in (4, '4'):
        v = tag_118.get(k)
        if isinstance(v, dict) and v:
            skin_data = v
            break

    if skin_data is None:
        skin_data = tag_118

    if not isinstance(skin_data, dict):
        return {}

    skin_types = {
        6: "Supreme Skins",
        5: "Grand Skins",
        4: "Exquisite Skins",
        3: "Deluxe Skins",
        2: "Exceptional Skins",
        1: "Common Skins"
    }

    skin_counts = {}
    total_skins = 0

    for skin_id, count in skin_data.items():
        try:
            skin_id_int = int(skin_id)
        except (ValueError, TypeError):
            continue
        if skin_id_int in skin_types:
            skin_counts[skin_types[skin_id_int]] = count
            total_skins += count

    if total_skins > 0:
        skin_counts["Total Skins"] = total_skins

    return skin_counts


_RANK_DEFINITIONS = [
    (0, 3, "Warrior III"), (4, 7, "Warrior II"), (8, 11, "Warrior I"),
    (12, 16, "Elite III"), (17, 21, "Elite II"), (22, 26, "Elite I"),
    (27, 31, "Master IV"), (32, 36, "Master III"), (37, 41, "Master II"), (42, 46, "Master I"),
    (47, 52, "Grandmaster V"), (53, 58, "Grandmaster IV"), (59, 64, "Grandmaster III"),
    (65, 70, "Grandmaster II"), (71, 76, "Grandmaster I"),
    (77, 82, "Epic V"), (83, 88, "Epic IV"), (89, 94, "Epic III"),
    (95, 100, "Epic II"), (101, 106, "Epic I"),
    (107, 112, "Legend V"), (113, 118, "Legend IV"), (119, 124, "Legend III"),
    (125, 130, "Legend II"), (131, 136, "Legend I"),
]


def map_rank(p: int) -> str:
    for lo, hi, name in _RANK_DEFINITIONS:
        if lo <= p <= hi:
            return name
    if 137 <= p <= 161:
        return f"Mythic {p - 136}"
    if 162 <= p <= 186:
        return f"Mythical Honor {p - 136}"
    if 187 <= p <= 236:
        return f"Mythical Glory {p - 136}"
    if 237 <= p <= 9999:
        return f"Mythical Immortal {p - 136}"
    return "Unknown"


def format_timestamp(timestamp: int) -> str:
    try:
        if timestamp == 0:
            return "Never"
        return datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "Unknown"


def format_timestamp_full(timestamp: int) -> str:
    try:
        if timestamp == 0:
            return "N/A"
        utc_dt = datetime.datetime.utcfromtimestamp(timestamp)
        pht_dt = utc_dt + datetime.timedelta(hours=8)
        return pht_dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "Invalid timestamp"


def extract_player_data(result, role_info=None, creation_ts=0) -> Optional[Dict]:
    if not result or not result[0] or len(result[0]) == 0:
        return None
    try:
        player = result[0][0]

        nickname = player.get(2, "Unknown")
        player_id = player.get(0, "Unknown")
        server = player.get(1, "Unknown")
        level = player.get(3, "Unknown")
        skin = player.get(83, "Unknown")
        hero_count = role_info.get(9, 0) if role_info else 0
        matches = role_info.get(22, 0) if role_info else 0

        location = "NOT FOUND"
        loc_data = player.get(71)
        if loc_data and isinstance(loc_data, list) and len(loc_data) >= 2:
            location = ", ".join(loc_data)

        last_login = player.get(5, 0)
        last_login_country = player.get(87, "Unknown")
        create_account_country = player.get(97, "Unknown")

        squad_icon = player.get(31, "")
        squad_name = player.get(30, "").replace("`", "").strip()
        squad = f"{squad_icon} {squad_name}".strip() if squad_name else "—"

        squad_id = 0
        if role_info and isinstance(role_info, dict):
            squad_id = role_info.get(34, 0)
        if not squad_id:
            squad_id = player.get(34, player.get(28, 0))

        tag_95 = player.get(95)
        tag_8 = player.get(8)
        high_rank = map_rank(tag_95) if tag_95 is not None else "Unknown"
        current_rank = map_rank(tag_8) if tag_8 is not None else "Unknown"
        achievement_points = player.get(7, 0)

        tag_136 = player.get(136, {})
        collector_point = tag_136.get(9, 0) if isinstance(tag_136, dict) else 0
        collector_rank = tag_136.get(10, 0) if isinstance(tag_136, dict) else 0
        collector_tier = map_collector_point(collector_point)

        tag_91 = player.get(91, [])
        hero_history = get_hero_history(tag_91) if tag_91 else ["Private / Not Available"]

        skin_counts = {}
        if role_info and isinstance(role_info, dict):
            tag_118 = role_info.get(118, {})
            if isinstance(tag_118, dict):
                skin_counts = parse_skin_counts(tag_118)

        rating_score = player.get(9, 0)

        followers = 0
        if role_info and isinstance(role_info, dict):
            followers = role_info.get(23, 0)
        if not followers:
            followers = player.get(15, 0)

        popularity = player.get(14, 0)

        likes = 0
        if role_info and isinstance(role_info, dict):
            likes = role_info.get(24, 0)
        if not likes:
            likes = player.get(61, 0)

        _t111 = player.get(111, {})
        if isinstance(_t111, dict):
            _cs_current = _t111.get(0, 0)
            credits_score = f"{_cs_current}/110" if _cs_current else "N/A"
        else:
            _cs_int = int(_t111) if _t111 else 0
            credits_score = f"{_cs_int}/110" if _cs_int else "N/A"

        restriction_flags = "None"
        _flags_val = 0
        if role_info and isinstance(role_info, dict):
            _flags_val = role_info.get(102, 0)
        if not _flags_val:
            _t135 = player.get(135, {})
            if isinstance(_t135, dict):
                _flags_val = _t135.get(0, 0)
        if _flags_val:
            _set_bits = bin(int(_flags_val)).count('1')
            _total_bits = 7
            _pct = round((_set_bits / _total_bits) * 100, 1)
            if _pct < 30:
                _risk, _risk_icon = "Low Risk", "✅"
            elif _pct < 60:
                _risk, _risk_icon = "Medium Risk", "⚠️"
            else:
                _risk, _risk_icon = "High Risk", "🚨"
            restriction_flags = f"{_pct}% {_risk_icon} ({_risk})"

        _t135 = player.get(135, {})
        _aff_level = _t135.get(1, 0) if isinstance(_t135, dict) else 0
        _AFFINITY_MAP = {0: "None", 1: "Bronze", 2: "Silver", 3: "Gold", 4: "Platinum", 5: "Diamond"}
        affinity_label = _AFFINITY_MAP.get(_aff_level, f"Level {_aff_level}") if _aff_level else "None"

        import time as _time
        _sl_expiry = player.get(50, 0)
        if _sl_expiry and isinstance(_sl_expiry, int) and _sl_expiry > _time.time():
            starlight_user = "Yes ⭐"
        else:
            starlight_user = "No"

        _MIN_VALID_TS = 1451577600
        _create_ts_fallback = player.get(6, 0)
        if creation_ts and creation_ts >= _MIN_VALID_TS:
            creation_date = format_timestamp_full(creation_ts)
        elif _create_ts_fallback and _create_ts_fallback >= _MIN_VALID_TS:
            creation_date = format_timestamp_full(_create_ts_fallback)
        else:
            creation_date = "N/A"

        _tag45 = player.get(45, {})
        if isinstance(_tag45, dict) and _tag45:
            _hero_entries = []
            for _entry in _tag45.values():
                if isinstance(_entry, dict):
                    _hid = _entry.get(0, 0)
                    _hts = _entry.get(1, 0)
                    _hname = HERO_ID_MAP.get(_hid, f"Unknown({_hid})")
                    _hero_entries.append((_hts, _hname))
            _hero_entries.sort(key=lambda x: x[0], reverse=True)
            last_heroes_purchase = ", ".join(h for _, h in _hero_entries) if _hero_entries else "N/A"
        else:
            _hero_buy_ts = player.get(175, 0)
            last_heroes_purchase = format_timestamp(_hero_buy_ts) if _hero_buy_ts else "N/A"

        mcl_wins = 0
        if role_info and isinstance(role_info, dict):
            mcl_wins = role_info.get(46, 0)
        if not mcl_wins:
            mcl_wins = player.get(104, player.get(103, 0))

        win_count = 0
        if role_info and isinstance(role_info, dict):
            win_count = role_info.get(22, 0)

        total_battles = 0
        if role_info and isinstance(role_info, dict):
            total_battles = role_info.get(77, 0)
        if not total_battles:
            total_battles = player.get(17, 0)

        if total_battles > 0:
            win_rate = f"{(win_count / total_battles * 100):.1f}%"
        else:
            win_rate = "N/A"

        bp = 0
        if role_info and isinstance(role_info, dict):
            _bp_raw = role_info.get(111, 0)
            if isinstance(_bp_raw, int):
                bp = _bp_raw
            elif isinstance(_bp_raw, dict):
                bp = _bp_raw.get(0, 0)

        squad_motto = "N/A"
        if role_info and isinstance(role_info, dict):
            _motto = role_info.get(24, "")
            if _motto and isinstance(_motto, str):
                squad_motto = _motto

        diamonds = 0
        if role_info and isinstance(role_info, dict):
            diamonds = role_info.get(46, 0)

        starlight_count = 0
        if role_info and isinstance(role_info, dict):
            starlight_count = role_info.get(60, 0)

        skin_history = []
        if role_info and isinstance(role_info, dict):
            _tag92 = role_info.get(92, [])
            if isinstance(_tag92, list):
                for _entry in _tag92[:10]:
                    if isinstance(_entry, dict):
                        _sid = _entry.get(0, 0)
                        _tier = _entry.get(2, 0)
                        _ts = _entry.get(4, 0)
                        _tier_name = {1: "Common", 2: "Exceptional", 3: "Deluxe",
                                      4: "Exquisite", 5: "Grand", 6: "Supreme"}.get(_tier, f"T{_tier}")
                        _date = format_timestamp(_ts) if _ts else "?"
                        skin_history.append(f"SkinID:{_sid}({_tier_name})|{_date}")
        skin_history_str = ", ".join(skin_history) if skin_history else "N/A"

        _EMBLEM_MAP = {1: "Fighter", 2: "Assassin", 3: "Mage", 4: "Marksman",
                       5: "Support", 6: "Tank", 7: "Common"}
        emblem_levels = "N/A"
        if role_info and isinstance(role_info, dict):
            _tag101 = role_info.get(101, {})
            if isinstance(_tag101, dict) and _tag101:
                _parts = []
                for _eid in sorted(_tag101.keys()):
                    _ename = _EMBLEM_MAP.get(_eid, f"E{_eid}")
                    _parts.append(f"{_ename}:Lv{_tag101[_eid]}")
                emblem_levels = ", ".join(_parts) if _parts else "N/A"

        _skin_ts = player.get(176, 0)
        latest_skin_date = format_timestamp(_skin_ts) if _skin_ts else "N/A"

        _latest_skin_id = player.get(175, 0)
        latest_skin_id_str = str(_latest_skin_id) if _latest_skin_id else "N/A"
        latest_skin_tier = get_skin_tier(_latest_skin_id) if _latest_skin_id else "N/A"

        bindings = "N/A"
        _bindings = player.get(47, {})
        if isinstance(_bindings, dict) and _bindings:
            binding_types = {
                0: "Facebook", 1: "Google", 2: "VK", 3: "Twitter",
                4: "Game Center", 5: "Moonton", 6: "Email", 7: "Phone"
            }
            binding_list = []
            for btype, bval in _bindings.items():
                try:
                    btype_int = int(btype)
                    bname = binding_types.get(btype_int, f"Type{btype_int}")
                    binding_list.append(bname)
                except Exception:
                    pass
            bindings = ", ".join(binding_list) if binding_list else "N/A"

        return {
            'status': 'success',
            'data': {
                'basic_info': {
                    'nickname': nickname,
                    'player_id': player_id,
                    'server': server,
                    'level': level,
                    'skin_count': skin,
                    'hero_count': hero_count,
                },
                'skin_info': {
                    'skin_breakdown': skin_counts,
                },
                'location_info': {
                    'location': location,
                    'last_login': format_timestamp(last_login),
                    'last_login_country': last_login_country,
                    'create_account_country': create_account_country,
                },
                'game_info': {
                    'current_rank': current_rank,
                    'high_rank': high_rank,
                    'achievement_points': achievement_points,
                    'squad': squad,
                    'squad_id': squad_id,
                    'hero_history': hero_history,
                    'matches': matches,
                },
                'collector_info': {
                    'collector_point': collector_point,
                    'collector_tier': collector_tier,
                    'collector_rank': collector_rank,
                },
                'security_info': {
                    'v2l_status': 'No',
                    'bindings': bindings,
                },
                'extra_info': {
                    'rating_score': rating_score,
                    'followers': followers,
                    'popularity': popularity,
                    'likes': likes,
                    'credits_score': credits_score if credits_score != "N/A" else None,
                    'restriction_flags': restriction_flags,
                    'affinity': affinity_label,
                    'starlight_user': starlight_user,
                    'creation_date': creation_date,
                    'last_heroes_purchase': last_heroes_purchase,
                    'mcl_champion_wins': mcl_wins,
                    'win_count': win_count,
                    'total_battles': total_battles,
                    'win_rate': win_rate,
                    'battle_points': bp if bp else None,
                    'squad_motto': squad_motto if squad_motto != "N/A" else None,
                    'diamonds': diamonds if diamonds else None,
                    'starlight_count': starlight_count if starlight_count else None,
                    'skin_history': skin_history_str if skin_history_str != "N/A" else None,
                    'emblem_levels': emblem_levels if emblem_levels != "N/A" else None,
                    'latest_skin_date': latest_skin_date,
                    'latest_skin_id': latest_skin_id_str,
                    'latest_skin_tier': latest_skin_tier,
                },
                'raw_data': player,
            },
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# DeviceManager
# FIX: _load() now deduplicates entries and validates minimum length (88 chars).
# Original only checked startswith('and_'); duplicates would waste rotation
# slots and a malformed short entry could produce empty imei_md5/android_id.
# ---------------------------------------------------------------------------

#: Minimum valid device-string length based on the actual devices.txt format:
#: 4 (prefix) + 32 (MD5) + 16 (android_id) + 36 (UUID) = 88 characters.
_DEVICE_MIN_LEN = 88


class DeviceManager:
    def __init__(self, devices_file: str = None):
        if not devices_file:
            p = os.path.join(_HERE, "devices.txt")
            devices_file = p if os.path.isfile(p) else "devices.txt"
        self.devices = self._load(devices_file)
        self.lock = threading.Lock()
        self.failed_devices: set = set()
        self.device_usage: Dict[str, int] = defaultdict(int)

    @staticmethod
    def _load(filename: str) -> List[str]:
        """Load device strings from *filename*.

        Changes from original:
        - Deduplicates entries (set-based seen tracker).
        - Skips entries shorter than _DEVICE_MIN_LEN (avoids feeding truncated
          strings to GameConnection which would produce empty imei_md5 /
          android_id fields).
        - Catches UnicodeDecodeError separately so a corrupt file produces a
          clear warning rather than silently falling back.
        """
        devices: List[str] = []
        seen: set = set()
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if (
                        line.startswith('and_')
                        and len(line) >= _DEVICE_MIN_LEN
                        and line not in seen
                    ):
                        seen.add(line)
                        devices.append(line)
        except FileNotFoundError:
            pass
        except UnicodeDecodeError as exc:
            import sys
            print(
                f"[DeviceManager] WARNING: could not decode {filename!r}: {exc}",
                file=sys.stderr,
            )
        if not devices:
            devices = [
                "and_33c9084d10d104e2e0e95288782a92ff3h0ixfjcdk5dm3i9deffa6fb-7f6c-4b46-bcc3-a52ab97c367c",
                "and_8f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0123456789abcdef01234567-0123-4567-89ab-cdef0123",
            ]
        return devices

    def get_next_device(self, exclude_device: Optional[str] = None) -> Optional[str]:
        with self.lock:
            if not self.devices:
                return None
            max_attempts = min(100, len(self.devices))
            for _ in range(max_attempts):
                device = random.choice(self.devices)
                if device != exclude_device and device not in self.failed_devices:
                    self.device_usage[device] += 1
                    return device

            if self.failed_devices:
                self.failed_devices.clear()
                device = random.choice(self.devices)
                if device != exclude_device:
                    self.device_usage[device] += 1
                    return device
            return None

    def mark_device_failure(self, device_id: str):
        with self.lock:
            self.failed_devices.add(device_id)

    def reset_device_failure(self, device_id: str):
        with self.lock:
            self.failed_devices.discard(device_id)


class BaseConnection:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sequence = 1
        self.socket: Optional[socket.socket] = None
        self.queue_data = b''

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.cleanup()

    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(8)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.connect((self.host, self.port))

    def cleanup(self):
        if self.socket:
            try:
                self.socket.setsockopt(
                    socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0)
                )
                self.socket.close()
            except Exception:
                pass
            self.socket = None
            self.sequence = 1

    def send_data(self, cmd_id: int, sdp: SdpStruct):
        packet = SdpStruct({0: cmd_id, 1: self.sequence, 5: sdp.data}).data
        buf = zstd.compress(packet)
        flags = (len(buf) + 4) | (16 << 24)
        self.socket.send(flags.to_bytes(4, 'big') + buf)
        self.sequence += 1

    def recv_data(self) -> Tuple[Optional[int], Optional[SdpStruct]]:
        try:
            while len(self.queue_data) < 4:
                try:
                    data = self.socket.recv(4096)
                    if not data:
                        return None, None
                    self.queue_data += data
                except socket.timeout:
                    return -1, None

            flags = int.from_bytes(self.queue_data[:4], 'big')
            size = flags & 0xFFFFFF
            compression_type = flags >> 24

            wait_count = 0
            while len(self.queue_data) < size:
                try:
                    data = self.socket.recv(4096)
                    if not data:
                        return None, None
                    self.queue_data += data
                    wait_count = 0
                except socket.timeout:
                    wait_count += 1
                    if wait_count >= 1:
                        return -1, None

            data = self.queue_data[4:size]
            self.queue_data = self.queue_data[size:]

            if compression_type == 1:
                data = zlib.decompress(data)
            elif compression_type == 16:
                data = zstd.decompress(data)
            elif compression_type == 2:
                cipher = AES.new(AES_KEY, AES.MODE_CBC, iv=AES_IV)
                data = cipher.decrypt(data[:-1] if len(data) % 16 else data).rstrip(b'\x00')
            elif compression_type == 3:
                cipher = AES.new(AES_KEY, AES.MODE_CBC, iv=AES_IV)
                data = cipher.decrypt(data[:-1] if len(data) % 16 else data).rstrip(b'\x00')
                data = zlib.decompress(data)
            elif compression_type == 18:
                cipher = AES.new(AES_KEY, AES.MODE_CBC, iv=AES_IV)
                dec = cipher.decrypt(data[:-1] if len(data) % 16 else data)
                data = zstd.decompress(dec.rstrip(b'\x00'))

            result = SdpStruct(data)
            cmd = result.get(0)
            if cmd is None:
                return None, None

            res = result.get(6) or result.get(5)
            if not res or not isinstance(res, bytes):
                return cmd, None

            return cmd, SdpStruct(res)

        except socket.timeout:
            return -1, None
        except Exception:
            return None, None


class GameConnection(BaseConnection):

    LOGIN_HOST = 'global-login.ml.youngjoygame.com'
    LOGIN_PORT = 30021

    def __init__(self, device_id: str, device_model: Optional[str] = None,
                 device_manager: Optional[DeviceManager] = None):
        super().__init__(self.LOGIN_HOST, self.LOGIN_PORT)
        self.device_id = device_id
        self.device_model = device_model or random.choice(DEVICE_MODELS)
        self.device_manager = device_manager

        parts = self.device_id.split('_')
        device_info = '_'.join(parts[1:]) if len(parts) >= 2 else device_id
        self.imei_md5 = device_info[:32] if len(device_info) >= 32 else device_info
        self.android_id = device_info[32:48] if len(device_info) >= 48 else ""
        self.advertising_id = device_info[48:] if len(device_info) > 48 else ""

        self.channel = 'and_usa'
        self.client_version = '2.2.23.1235.1'
        self.account_id = 0
        self.session_key = ''
        self.zone_id = 0
        self.game_server_host = ''
        self.game_server_port = 0
        self.creation_ts = 0

    def login_to_login_server(self) -> bool:
        try:
            if self.host != self.LOGIN_HOST or self.port != self.LOGIN_PORT:
                self.cleanup()
                self.host = self.LOGIN_HOST
                self.port = self.LOGIN_PORT
                self.connect()

            login_data = SdpStruct({
                0: self.device_id,
                1: (f'gps_adid={self.advertising_id}'
                    f'&android_id={self.android_id}'
                    f'&device_unique_id={self.imei_md5}'),
                2: self.client_version,
                3: self.channel,
                4: 'en',
            })
            self.send_data(1, login_data)

            for _ in range(8):
                cmd, res = self.recv_data()
                if cmd is None or cmd == -1:
                    break
                if cmd != 2 or not res:
                    continue
                self.account_id = res.get(0)
                self.session_key = res.get(1)
                z = res.get(2)
                if hasattr(z, 'get'):
                    self.zone_id = z.get(0) or 0
                elif isinstance(z, (list, tuple)) and z:
                    self.zone_id = z[0]
                else:
                    self.zone_id = z or 0
                self.creation_ts = res.get(19, 0)
                if self.account_id is not None and self.session_key:
                    return True
                break
        except Exception:
            pass
        return False

    def get_game_server(self) -> bool:
        try:
            req = SdpStruct({
                0: self.account_id, 1: self.session_key, 2: self.client_version,
                5: self.zone_id, 6: self.channel,
            })
            self.send_data(5, req)
            for _ in range(8):
                cmd, res = self.recv_data()
                if cmd is None or cmd == -1:
                    break
                if cmd == 6 and res:
                    host_port = res.get(1) if hasattr(res, 'get') else res[1]
                    self.game_server_host, port_str = str(host_port).split(':')
                    self.game_server_port = int(port_str)
                    return True
        except Exception:
            pass
        return False

    def connect_to_game_server(self, max_retries: int = 2) -> bool:
        for attempt in range(max_retries):
            try:
                self.cleanup()
                self.host = self.game_server_host
                self.port = self.game_server_port
                self.connect()

                auth = SdpStruct({
                    0: self.account_id, 1: self.session_key, 2: self.zone_id,
                    4: self.client_version, 13: self.channel, 15: self.device_id,
                })
                self.send_data(10001, auth)
                self.send_data(10101, SdpStruct({0: 0, 2: 2}))

                for _ in range(12):
                    cmd, ac_res = self.recv_data()
                    if cmd is None:
                        break
                    if cmd == 10002:
                        dead = False
                        try:
                            self.socket.settimeout(0.35)
                            for _ in range(8):
                                c2, _ = self.recv_data()
                                if c2 is None:
                                    dead = True
                                    break
                                if c2 == -1:
                                    break
                        except Exception:
                            pass
                        try:
                            self.socket.settimeout(8)
                        except Exception:
                            pass
                        if dead:
                            break
                        return True
                    if cmd == -1:
                        break

                if attempt < max_retries - 1:
                    time.sleep(1)
            except Exception:
                if attempt < max_retries - 1:
                    time.sleep(1)
        return False

    def get_account_info(self, guid: int, session: str,
                         account_type: str = "and") -> Optional[SdpStruct]:
        try:
            payloads = [
                SdpStruct({
                    0: f"mt-{account_type}_{guid}",
                    1: f"token={session}&name=&id={guid}&nid=",
                    2: 0,
                }),
                SdpStruct({
                    0: f"mt-{account_type}_{guid}",
                    1: f"token={session}",
                    2: 0,
                }),
                SdpStruct({
                    0: str(guid),
                    1: session,
                    2: 0,
                })
            ]

            for req in payloads[:1]:
                self.send_data(10207, req)
                for _ in range(6):
                    cmd, res = self.recv_data()
                    if cmd is None or cmd == -1:
                        break
                    if cmd == 10208 and res:
                        return res
        except Exception:
            pass
        return None

    def get_highest_level_role(self, account_result) -> Tuple[Optional[int], Optional[int]]:
        if not account_result:
            return None, None
        role_list = account_result.get(2)
        if not role_list:
            return None, None

        highest_role = None
        highest_level = 0

        for role in role_list:
            if isinstance(role, SdpStruct):
                zone = role.get(0, 0)
                rid = role.get(1, 0)
                lvl = role.get(3, 0)
            else:
                zone = role[0] if len(role) > 0 else 0
                rid = role[1] if len(role) > 1 else 0
                lvl = role[3] if len(role) > 3 else 0

            if lvl > highest_level:
                highest_level = lvl
                highest_role = (rid, zone)

        return highest_role if highest_role else (None, None)

    def get_role_detail(self, role_id: int, zone_id: int = 0) -> Optional[SdpStruct]:
        try:
            self.send_data(11153, SdpStruct({1: role_id}))
            timeout_count = 0
            for _ in range(16):
                cmd, res = self.recv_data()
                if cmd is None:
                    return None
                if cmd in (20001, 20002, 11191):
                    continue
                if cmd == -1:
                    timeout_count += 1
                    if timeout_count >= 3:
                        break
                    continue
                if cmd == 11154:
                    return res
        except Exception:
            pass
        return None

    def get_role_info(self, role_id: int, zone_id: int) -> Optional[SdpStruct]:
        try:
            self.send_data(10143, SdpStruct({0: role_id, 1: zone_id}))
            timeout_count = 0
            while timeout_count < 2:
                cmd, res = self.recv_data()
                if cmd is None:
                    break
                if cmd == -1:
                    timeout_count += 1
                    break
                if cmd == 10144:
                    return res
        except Exception:
            pass
        return None

    def filter_by_server(self, result, target_server):
        if not result or not result.get(0):
            return None
        players_list = result[0]
        for player in players_list:
            if isinstance(player, dict):
                player_server = player.get(1)
                if player_server == target_server:
                    return {0: [player]}
        return None


def get_player_info(
    guid: int,
    session: str,
    device_manager: DeviceManager,
    max_device_retries: int = 20,
) -> Optional[Dict]:

    used_devices: List[str] = []

    for attempt in range(1, max_device_retries + 1):
        exclude = used_devices[-1] if used_devices else None
        device_id = device_manager.get_next_device(exclude)
        if not device_id:
            break

        used_devices.append(device_id)
        conn: Optional[GameConnection] = None

        try:
            conn = GameConnection(device_id=device_id, device_manager=device_manager)
            conn.connect()

            if not conn.login_to_login_server():
                conn.cleanup()
                continue

            if not conn.get_game_server():
                conn.cleanup()
                continue

            if not conn.connect_to_game_server():
                conn.cleanup()
                continue

            result = conn.get_account_info(guid, session, "and")
            if not result:
                result = conn.get_account_info(guid, session, "ios")
            if not result:
                conn.cleanup()
                continue

            role_id, zone_id = conn.get_highest_level_role(result)
            if not role_id:
                conn.cleanup()
                continue

            role_detail = conn.get_role_detail(role_id)
            if not role_detail:
                conn.cleanup()
                continue

            role_info = conn.get_role_info(role_id, zone_id)

            player_data = extract_player_data(role_detail, role_info, conn.creation_ts)
            if not player_data:
                conn.cleanup()
                continue

            v2l = 'Yes' if result.get(13, 0) == 1 else 'No'
            player_data['data']['security_info']['v2l_status'] = v2l
            player_data['v2l_status'] = v2l
            player_data['device_used'] = device_id
            player_data['attempts'] = attempt

            # Flat player_data for checker UIs (v9/dashboard)
            try:
                basic = (player_data.get('data') or {}).get('basic_info') or {}
                game = (player_data.get('data') or {}).get('game_info') or {}
                col = (player_data.get('data') or {}).get('collector_info') or {}
                skin_info = (player_data.get('data') or {}).get('skin_info') or {}
                loc = (player_data.get('data') or {}).get('location_info') or {}
                sb = skin_info.get('skin_breakdown') or {}
                player_data['player_data'] = {
                    'nickname': basic.get('nickname'),
                    'level': basic.get('level'),
                    'skin': basic.get('skin_count') or sb.get('Total Skins') or sb.get('total'),
                    'hero_count': basic.get('hero_count'),
                    'current_rank': game.get('current_rank'),
                    'high_rank': game.get('high_rank'),
                    'collector_tier': col.get('collector_tier'),
                    'collector_point': col.get('collector_point'),
                    'squad': game.get('squad'),
                    'last_login': loc.get('last_login'),
                    'server': basic.get('server'),
                    'skin_breakdown': {
                        'Supreme': sb.get('Supreme Skins') or sb.get('Supreme') or 0,
                        'Grand': sb.get('Grand Skins') or sb.get('Grand') or 0,
                        'Exceptional': sb.get('Exceptional Skins') or sb.get('Exceptional') or 0,
                        'Deluxe': sb.get('Deluxe Skins') or sb.get('Deluxe') or 0,
                    },
                }
                # fix nickname from nested
                pd = player_data['player_data']
                if not pd.get('nickname'):
                    pd['nickname'] = basic.get('nickname')
            except Exception:
                pass

            conn.cleanup()
            return player_data

        except Exception:
            if conn:
                conn.cleanup()
            continue

    return None
