"""
ML Player Lookup Module
Clean version without debug prints
"""

import requests
import uuid
import time
import hashlib
import urllib3
import zlib
import zstandard as zstd
import socket
import datetime
import random
import struct
import os
import sys
from enum import Enum
from typing import Dict, List, Any, Union, Tuple
from Crypto.Cipher import AES

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
from sdp import SdpStruct, SdpDataType, SdpException

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================================================
# CONFIGURATION
# ============================================================================

HERO_ID_MAP = {
    1: "Miya", 2: "Balmond", 3: "Saber", 4: "Alice", 5: "Nana", 6: "Tigreal", 7: "Alucard", 8: "Karina", 9: "Akai",
    10: "Franco", 11: "Bane", 12: "Bruno", 13: "Clint", 14: "Rafaela", 15: "Eudora", 16: "Zilong", 17: "Fanny",
    18: "Layla", 19: "Minotaur", 20: "Lolita", 21: "Hayabusa", 22: "Freya", 23: "Gord", 24: "Natalia", 25: "Kagura",
    26: "Chou", 27: "Sun", 28: "Alpha", 29: "Ruby", 30: "Yi Sun-shin", 31: "Moskov", 32: "Johnson", 33: "Cyclops",
    34: "Estes", 35: "Hilda", 36: "Aurora", 37: "Lapu-Lapu", 38: "Vexana", 39: "Roger", 40: "Karrie", 41: "Gatotkaca",
    42: "Harley", 43: "Irithel", 44: "Grock", 45: "Argus", 46: "Odette", 47: "Lancelot", 48: "Diggie", 49: "Hylos",
    50: "Zhask", 51: "Helcurt", 52: "Pharsa", 53: "Lesley", 54: "Jawhead", 55: "Angela", 56: "Gusion", 57: "Valir",
    58: "Martis", 59: "Uranus", 60: "Hanabi", 61: "Chang'e", 62: "Kaja", 63: "Selena", 64: "Aldous", 65: "Claude",
    66: "Vale", 67: "Leomord", 68: "Lunox", 69: "Hanzo", 70: "Belerick", 71: "Kimmy", 72: "Thamuz", 73: "Harith",
    74: "Minsitthar", 75: "Kadita", 76: "Faramis", 77: "Badang", 78: "Khufra", 79: "Granger", 80: "Guinevere",
    81: "Esmeralda", 82: "Terizla", 83: "X.Borg", 84: "Ling", 85: "Dyrroth", 86: "Lylia", 87: "Baxia", 88: "Masha",
    89: "Wanwan", 90: "Silvanna", 91: "Cecilion", 92: "Carmilla", 93: "Atlas", 94: "Popol and Kupa", 95: "Yu Zhong",
    96: "Luo Yi", 97: "Benedetta", 98: "Khaleed", 99: "Barats", 100: "Brody", 101: "Yve", 102: "Mathilda",
    103: "Paquito", 104: "Gloo", 105: "Beatrix", 106: "Phoveus", 107: "Natan", 108: "Aulus", 109: "Aamon",
    110: "Valentina", 111: "Edith", 112: "Floryn", 113: "Yin", 114: "Melissa", 115: "Xavier", 116: "Julian",
    117: "Fredrinn", 118: "Joy", 119: "Novaria", 120: "Arlott", 121: "Ixia", 122: "Nolan", 123: "Cici",
    124: "Chip", 125: "Zhuxin", 126: "Suyou", 127: "Lukas", 128: "Kalea", 129: "Obsidia", 130: "Zetian",
    131: "Sora", 132: "Marcel", 133: "Unknown", 134: "Hirara"
}

DEVICE_MODELS = [
    'Xiaomi:Redmi Note 12',
    'Samsung:Galaxy S21',
    'OnePlus:OnePlus 9',
    'OPPO:OPPO A78',
    'Vivo:vivo Y35'
]

AES_KEY = bytes.fromhex('f5a193d50ade553e9835595f5cd75ddd')
AES_IV = b'\x00' * 16

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_hero_history(tag_91):
    return [HERO_ID_MAP.get(hid, f"Unknown({hid})") for hid in reversed(tag_91)]

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
                return name
            per_level = (max_p - min_p) / 5
            level = int((point - min_p) // per_level)
            roman = ["V", "IV", "III", "II", "I"][level]
            return f"{name} {roman}"
    return "Unknown"

def map_rank(p):
    RANK_DEFINITIONS = [
        {"min": 0, "max": 4, "rank": "Warrior III"},
        {"min": 5, "max": 9, "rank": "Warrior II"},
        {"min": 10, "max": 14, "rank": "Warrior I"},
        {"min": 15, "max": 19, "rank": "Elite IV"},
        {"min": 20, "max": 24, "rank": "Elite III"},
        {"min": 25, "max": 29, "rank": "Elite II"},
        {"min": 30, "max": 34, "rank": "Elite I"},
        {"min": 35, "max": 39, "rank": "Master IV"},
        {"min": 40, "max": 44, "rank": "Master III"},
        {"min": 45, "max": 49, "rank": "Master II"},
        {"min": 50, "max": 54, "rank": "Master I"},
        {"min": 55, "max": 59, "rank": "Grandmaster IV"},
        {"min": 60, "max": 64, "rank": "Grandmaster III"},
        {"min": 65, "max": 69, "rank": "Grandmaster II"},
        {"min": 70, "max": 74, "rank": "Grandmaster I"},
        {"min": 75, "max": 79, "rank": "Epic IV"},
        {"min": 80, "max": 84, "rank": "Epic III"},
        {"min": 85, "max": 89, "rank": "Epic II"},
        {"min": 90, "max": 94, "rank": "Epic I"},
        {"min": 95, "max": 99, "rank": "Legend IV"},
        {"min": 100, "max": 104, "rank": "Legend III"},
        {"min": 105, "max": 109, "rank": "Legend II"},
        {"min": 110, "max": 114, "rank": "Legend I"},
        {"min": 115, "max": 138, "rank": lambda p: f"Mythic {p - 114}"},
        {"min": 139, "max": 173, "rank": lambda p: f"Mythical Honor {p - 114}"},
        {"min": 174, "max": 213, "rank": lambda p: f"Mythical Glory {p - 136}"},
        {"min": 214, "max": 999, "rank": lambda p: f"Mythical Immortal {p - 136}"},
    ]
    for entry in RANK_DEFINITIONS:
        if entry["min"] <= p <= entry["max"]:
            rank = entry["rank"]
            return rank(p) if callable(rank) else rank
    return "Unknown"

def parse_skin_counts(tag_118, total_skins):
    if not tag_118 or not isinstance(tag_118, dict):
        return {
            "total": total_skins,
            "Common": total_skins,
            "Deluxe": 0,
            "Exceptional": 0,
            "Grand": 0,
            "Supreme": 0
        }
    
    field_4 = tag_118.get(4, {})
    
    if isinstance(field_4, dict):
        exceptional = field_4.get(2, 0)
        deluxe = field_4.get(3, 0)
        grand = field_4.get(5, 0)
        supreme = field_4.get(6, 0)
        special_skins = exceptional + deluxe + grand + supreme
        common = total_skins - special_skins
        
        return {
            "total": total_skins,
            "Common": common,
            "Exceptional": exceptional,
            "Deluxe": deluxe,
            "Grand": grand,
            "Supreme": supreme
        }
    else:
        return {
            "total": total_skins,
            "Common": total_skins,
            "Exceptional": 0,
            "Deluxe": 0,
            "Grand": 0,
            "Supreme": 0
        }

def load_device_ids_from_file(filename=None):
    if not filename:
        filename = os.path.join(_HERE, 'devices.txt')
        if not os.path.exists(filename):
            filename = 'devices.txt'
    if not os.path.exists(filename):
        return ['and_cd9e459ea708a948d5c2f5a6ca8838cf648efdbc9a8c3ce703fa556d-34a4-4cde-a061-34938d08a26e']
    
    try:
        device_ids = []
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    device_ids.append(line)
        
        if not device_ids:
            return ['and_cd9e459ea708a948d5c2f5a6ca8838cf648efdbc9a8c3ce703fa556d-34a4-4cde-a061-34938d08a26e']
        
        return device_ids
    except Exception:
        return ['and_cd9e459ea708a948d5c2f5a6ca8838cf648efdbc9a8c3ce703fa556d-34a4-4cde-a061-34938d08a26e']

DEVICE_IDS = load_device_ids_from_file()

def remove_failed_device_id(failed_device_id):
    global DEVICE_IDS
    if failed_device_id in DEVICE_IDS:
        DEVICE_IDS.remove(failed_device_id)
        return True
    return False

# ============================================================================
# CONNECTION
# ============================================================================

class BaseConnection:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sequence = 1
        self.socket = None
        self.queue_data = b''
        self.last_header_size = 0

    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc, tb):
        self.cleanup()

    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(8)
        self.socket.connect((self.host, self.port))

    def cleanup(self):
        if self.socket:
            self.socket.close()
            self.sequence = 1
            self.socket = None

    def send_data(self, id, sdp):
        packet = SdpStruct({0: id, 1: self.sequence, 5: sdp.data}).data
        buf = zstd.compress(packet)
        flags = (len(buf) + 4) | (16 << 24)
        buf = flags.to_bytes(4, 'big') + buf
        self.socket.send(buf)
        self.sequence += 1

    def recv_data(self):
        try:
            while len(self.queue_data) < 4:
                data = self.socket.recv(4096)
                if not data:
                    return None, None
                self.queue_data += data

            flags = int.from_bytes(self.queue_data[:4], 'big')
            size = flags & 0xFFFFFF
            compression_type = flags >> 24
            self.last_header_size = size
            
            while len(self.queue_data) < size:
                data = self.socket.recv(4096)
                if not data:
                    return None, None
                self.queue_data += data

            data = self.queue_data[4:size]
            self.queue_data = self.queue_data[size:]
            
            if compression_type == 1:
                data = zlib.decompress(data)
            elif compression_type == 16:
                data = zstd.decompress(data)
            elif compression_type == 2:
                cipher = AES.new(AES_KEY, AES.MODE_CBC, iv=AES_IV)
                data = cipher.decrypt(data[:-1] if len(data) % 16 != 0 else data).rstrip(b'\x00')
            elif compression_type == 3:
                cipher = AES.new(AES_KEY, AES.MODE_CBC, iv=AES_IV)
                data = cipher.decrypt(data[:-1] if len(data) % 16 != 0 else data).rstrip(b'\x00')
                data = zlib.decompress(data)
            elif compression_type == 18:
                cipher = AES.new(AES_KEY, AES.MODE_CBC, iv=AES_IV)
                decrypted = cipher.decrypt(data[:-1] if len(data) % 16 != 0 else data)
                data = zstd.decompress(decrypted.rstrip(b'\x00'))

            result = SdpStruct(data)
            id = result[0]
            if id is None:
                return None, None

            res = result.get(6) or result.get(5)
            if not res or not isinstance(res, bytes):
                return id, None

            return id, SdpStruct(res)
        except socket.timeout:
            return -1, None
        except:
            return None, None

class GameConnection(BaseConnection):
    def __init__(self, device_id, device_model=None):
        super().__init__('login.ml.youngjoygame.com', 30021)
        self.device_id = device_id
        self.device_model = device_model or "Xiaomi:Redmi Note 12"
    
        parts = self.device_id.split('_')
        if len(parts) >= 2:
            device_info = parts[1]
            if len(parts) >= 3 and len(device_info) < 32:
                device_info = device_info + "_" + parts[2]
                
            if len(device_info) >= 32:
                self.imei_md5 = device_info[:32]
                self.android_id = device_info[32:48] if len(device_info) >= 48 else ""
                self.advertising_id = device_info[48:] if len(device_info) > 48 else ""
            else:
                self.imei_md5 = device_info
                self.android_id = ""
                self.advertising_id = ""
        else:
            self.imei_md5 = device_id
            self.android_id = ""
            self.advertising_id = ""
        
        self.channel = 'and_usa'
        self.client_version = '2.2.16.1235.1'
        self.account_id = 0
        self.session_key = ''
        self.zone_id = 0
        self.game_server_host = ''
        self.game_server_port = 0

    def login_to_login_server(self):
        if self.host != 'login.ml.youngjoygame.com' or self.port != 30021:
            self.cleanup()
            self.host = 'login.ml.youngjoygame.com'
            self.port = 30021
            self.connect()
        
        self.send_data(1, SdpStruct({
            0: self.device_id,
            1: f'gps_adid={self.advertising_id}&android_id={self.android_id}&device_unique_id={self.imei_md5}',
            2: self.client_version,
            3: self.channel,
            4: 'en'
        }))

        id, res = self.recv_data()
        if id == 2 and res:
            self.account_id = res.get(0)
            self.session_key = res.get(1)
            z = res.get(2)
            if hasattr(z, 'get'):
                self.zone_id = z.get(0) or 0
            elif isinstance(z, (list, tuple)) and z:
                self.zone_id = z[0]
            else:
                self.zone_id = z or 0
            if self.account_id is not None and self.session_key:
                return True
        return False

    def get_game_server(self):
        self.send_data(5, SdpStruct({
            0: self.account_id,
            1: self.session_key,
            2: self.client_version,
            5: self.zone_id,
            6: self.channel
        }))
        
        id, res = self.recv_data()
        if id == 6 and res:
            game_server = res[1]
            self.game_server_host, self.game_server_port = game_server.split(':')
            self.game_server_port = int(self.game_server_port)
            return True
        return False

    def connect_to_game_server(self):
        self.cleanup()
        self.host = self.game_server_host
        self.port = self.game_server_port
        self.connect()
        
        self.send_data(10001, SdpStruct({
            0: self.account_id,
            1: self.session_key,
            2: self.zone_id,
            4: self.client_version,
            13: self.channel,
            15: self.device_id
        }))
        
        self.send_data(10101, SdpStruct({0: 0, 2: 2}))
        
        for _ in range(20):
            id, res = self.recv_data()
            if id is None:
                return False
            elif id == 10002:
                return True
            elif id == -1:
                return False
        return False

    def lookup_player(self, search_value, search_type="id", server_filter=None):
        if search_type == "id":
            lookup_data = SdpStruct({1: int(search_value)})
        else:
            lookup_data = SdpStruct({0: str(search_value).strip()})
        
        self.send_data(11153, lookup_data)
        id_20001_count = 0
        
        for _ in range(30):
            id, res = self.recv_data()
            if id is None or id == -1:
                return None
            elif id == 11154:
                if search_type == "nickname" and server_filter is not None:
                    return self.filter_by_server(res, server_filter)
                return res
            elif id == 20001:
                id_20001_count += 1
                if self.last_header_size < 100 and id_20001_count >= 2:
                    return None
        return None
    
    def get_role_info(self, role_id: int, zone_id: int, max_retries=5):
        for attempt in range(max_retries):
            try:
                self.send_data(10143, SdpStruct({0: role_id, 1: zone_id}))
                timeout_count = 0
                
                while timeout_count < 10:
                    id, res = self.recv_data()
                    if id is None:
                        break
                    elif id == -1:
                        timeout_count += 1
                        if timeout_count < 10:
                            time.sleep(0.5)
                        else:
                            break
                    elif id == 10144:
                        return res
                    elif id == 20001:
                        continue
                
                if attempt < max_retries - 1:
                    time.sleep(0.1)
            except:
                if attempt < max_retries - 1:
                    time.sleep(0.1)
        return None
                    
    def filter_by_server(self, result, target_server):
        if not result or not result.get(0):
            return None
        
        for player in result[0]:
            if isinstance(player, dict) and player.get(1) == target_server:
                return {0: [player]}
        return None

    def __enter__(self):
        super().__enter__()
        if not self.login_to_login_server():
            raise ConnectionError("LOGIN_FAILED")
        if not self.get_game_server():
            raise ConnectionError("SERVER_SELECTION_FAILED")
        return self

# ============================================================================
# DATA EXTRACTION
# ============================================================================

def format_timestamp(timestamp):
    try:
        utc_dt = datetime.datetime.utcfromtimestamp(timestamp)
        wib_dt = utc_dt + datetime.timedelta(hours=7)
        return wib_dt.strftime("%Y-%m-%d %H:%M:%S") + " WIB"
    except:
        return "Invalid timestamp"

def extract_player_data(result, role_info=None):
    if not result or not result[0] or len(result[0]) == 0:
        return None
    
    try:
        player_data = result[0][0]
        
        extracted = {
            'nickname': player_data.get(2, "Unknown"),
            'player_id': player_data.get(0, "Unknown"),
            'server': player_data.get(1, "Unknown"),
            'level': player_data.get(3, "Unknown"),
            'skin': player_data.get(83, "Unknown"),
        }
        
        location_data = player_data.get(71, None)
        if location_data and isinstance(location_data, list) and len(location_data) >= 2:
            extracted['location'] = ", ".join(location_data)
        else:
            extracted['location'] = "NOT FOUND"
        
        last_login = player_data.get(5, 0)
        extracted['last_login'] = format_timestamp(last_login)
        extracted['last_login_country'] = player_data.get(87, "Unknown")
        extracted['create_account_country'] = player_data.get(97, "Unknown")
        
        squad_icon = player_data.get(31, "")
        squad_name = player_data.get(30, "").replace("`", "").strip()
        extracted['squad'] = f"{squad_icon} {squad_name}".strip() if squad_name else "—"

        tag_95 = player_data.get(95)
        tag_8 = player_data.get(8)
        extracted['high_rank'] = map_rank(tag_95) if tag_95 is not None else "Unknown"
        extracted['current_rank'] = map_rank(tag_8) if tag_8 is not None else "Unknown"
        extracted['achievement_points'] = player_data.get(7, 0)
        
        tag_136 = player_data.get(136, {})
        collector_point = tag_136.get(9, 0) if isinstance(tag_136, dict) else 0
        extracted['collector_point'] = collector_point
        extracted['collector_rank'] = tag_136.get(10, 0) if isinstance(tag_136, dict) else 0
        extracted['collector_tier'] = map_collector_point(collector_point)
        
        tag_91 = player_data.get(91, [])
        extracted['hero_history'] = get_hero_history(tag_91) if tag_91 else ["Private / Not Available"]
        
        if role_info:
            extracted['hero_count'] = role_info.get(9, 0)
            total_skins = role_info.get(10, 0)
            tag_118 = role_info.get(118, {})
            extracted['skin_breakdown'] = parse_skin_counts(tag_118, total_skins)
            
            field_92 = role_info.get(92, [])
            if isinstance(field_92, list) and len(field_92) > 0:
                timestamps = []
                for entry in field_92:
                    if isinstance(entry, (dict, SdpStruct)):
                        timestamp = entry.get(4, 0)
                        if timestamp and timestamp > 0:
                            timestamps.append(timestamp)
                
                if timestamps:
                    account_created_timestamp = min(timestamps)
                    extracted['account_created'] = format_timestamp(account_created_timestamp)
                    extracted['account_created_timestamp'] = account_created_timestamp
                    
                    try:
                        utc_dt = datetime.datetime.utcfromtimestamp(account_created_timestamp)
                        wib_dt = utc_dt + datetime.timedelta(hours=7)
                        ttl_date = wib_dt - datetime.timedelta(days=1)
                        extracted['ttl'] = ttl_date.strftime("%Y-%m-%d")
                    except:
                        extracted['ttl'] = "Unknown"
                else:
                    extracted['account_created'] = "Unknown"
                    extracted['account_created_timestamp'] = 0
                    extracted['ttl'] = "Unknown"
            else:
                extracted['account_created'] = "Unknown"
                extracted['account_created_timestamp'] = 0
                extracted['ttl'] = "Unknown"
            
            tag_94 = role_info.get(94, [])
            if isinstance(tag_94, list) and len(tag_94) > 0:
                top_heroes = []
                for entry in tag_94:
                    if isinstance(entry, (dict, SdpStruct)):
                        hero_id = entry.get(0)
                        if hero_id and hero_id in HERO_ID_MAP:
                            top_heroes.append(HERO_ID_MAP[hero_id])
                extracted['top3_most_used_heroes'] = ", ".join(top_heroes[:3]) if top_heroes else "Unknown"
            else:
                extracted['top3_most_used_heroes'] = "Unknown"
        else:
            extracted['hero_count'] = 0
            extracted['account_created'] = "Unknown"
            extracted['account_created_timestamp'] = 0
            extracted['ttl'] = "Unknown"
            extracted['top3_most_used_heroes'] = "Unknown"
            extracted['skin_breakdown'] = {
                "total": 0, "Common": 0, "Deluxe": 0,
                "Exceptional": 0, "Grand": 0, "Supreme": 0
            }
        
        return {'player_data': extracted}
    except:
        return None

# ============================================================================
# MAIN LOOKUP FUNCTION
# ============================================================================

def lookup_player_data(player_id_or_nickname, server_id=None):
    try:
        try:
            player_id = int(player_id_or_nickname)
            search_type = "id"
            search_value = player_id
            server_filter = None
        except ValueError:
            search_type = "nickname"
            search_value = str(player_id_or_nickname).strip()
            
            if not server_id:
                return {"error": "Server ID is required when searching by nickname", "status": "error"}
            
            try:
                server_filter = int(server_id)
            except ValueError:
                return {"error": "Server ID must be a number", "status": "error"}
        
        device_ids = DEVICE_IDS.copy()
        device_models = DEVICE_MODELS.copy()
        
        if not device_ids:
            return {"error": "No device IDs available", "status": "error"}
        
        retry_count = 0
        max_retries = 3
        result = None
        current_device_ids = device_ids.copy()
        
        while retry_count < max_retries and result is None and current_device_ids:
            current_device_id = random.choice(current_device_ids)
            current_device_model = random.choice(device_models) if device_models else None
            
            try:
                with GameConnection(device_id=current_device_id, device_model=current_device_model) as conn:
                    if not conn.connect_to_game_server():
                        if current_device_id in current_device_ids:
                            current_device_ids.remove(current_device_id)
                        retry_count += 1
                        continue
                    
                    result = conn.lookup_player(search_value, search_type, server_filter)
                    
                    if result is None:
                        retry_count += 1
                        continue
                    
                    if result and result.get(0) and len(result[0]) > 0:
                        player = result[0][0]
                        found_player_id = player.get(0)
                        found_server = player.get(1)
                        
                        role_info = None
                        if found_player_id and found_server:
                            role_info = conn.get_role_info(found_player_id, found_server)
                        
                        player_data = extract_player_data(result, role_info)
                        if player_data:
                            return {"status": "success", **player_data}
                        else:
                            return {"error": "Error extracting player data", "status": "error"}
                
            except ConnectionError as e:
                error_msg = str(e)
                if "LOGIN_FAILED" in error_msg:
                    remove_failed_device_id(current_device_id)
                
                if current_device_id in current_device_ids:
                    current_device_ids.remove(current_device_id)
                
                retry_count += 1
                if not current_device_ids:
                    current_device_ids = DEVICE_IDS.copy()
                    if not current_device_ids:
                        break
        
        if result:
            return {"error": "Player found but failed to extract data", "status": "error"}
        else:
            return {"error": "Player not found", "status": "error"}
            
    except Exception as e:
        return {"error": f"Internal server error: {str(e)}", "status": "error"}