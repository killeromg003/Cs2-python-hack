import ctypes
import json
import struct


class Offsets:
    # client.dll globals
    dwEntityList = 0x0
    dwLocalPlayerPawn = 0x0
    dwLocalPlayerController = 0x0
    dwCSGOInput = 0x0
    dwGlobalVars = 0x0
    dwForceAttack = 0x0
    dwForceJump = 0x0
    dwViewAngles = 0x0
    dwViewMatrix = 0x0
    dwGlowManager = 0x0
    dwGameRules = 0x0
    dwGameEntitySystem = 0x0

    # C_CSPlayerPawn / C_BaseEntity
    m_FlashBangTime = 0x0
    m_iIDEntIndex = 0x0
    m_iHealth = 0x0
    m_iTeamNum = 0x0
    m_lifeState = 0x0
    m_fFlags = 0x0
    m_pGameSceneNode = 0x0
    m_vOldOrigin = 0x0
    m_vecViewOffset = 0x0
    m_hPawn = 0x0
    m_bSpotted = 0x8

    # CCSPlayerController
    m_hPlayerPawn = 0x90C
    m_iPawnHealth = 0x918

    # Entity-list layout
    ENT_GROUP_STRIDE = 0x10
    ENT_ENTRY_OFFSET = 0x8
    ENT_SLOT_STRIDE = 0x78
    MAX_PLAYERS = 64
    m_entitySpottedState = 0x0
    m_modelState = 0x140

    @classmethod
    def load_from_json(cls, filepath: str) -> bool:
        """Load known offsets from a JSON file."""
        try:
            with open(filepath, "r", encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            print(f"[-] Offset file not found: {filepath}")
            return False
        except json.JSONDecodeError as error:
            print(f"[-] Invalid JSON in {filepath}: {error}")
            return False

        for key, value in data.items():
            if not hasattr(cls, key):
                continue
            if isinstance(value, str) and value.lower().startswith("0x"):
                value = int(value, 16)
            setattr(cls, key, value)

        print(f"[+] Offsets loaded from {filepath}")
        return True


class Buttons:
    IN_ATTACK = 1 << 0
    IN_JUMP = 1 << 1
    ATTACK_PRESS = IN_ATTACK | (1 << 16)
    ATTACK_RELEASE = 1 << 16
    JUMP_PRESS = IN_JUMP | (1 << 16)
    JUMP_RELEASE = 1 << 16


VK_SPACE = 0x20
VK_XBUTTON1 = 0x05
VK_F1 = 0x70
VK_F2 = 0x71
VK_F3 = 0x72
VK_F4 = 0x73


def is_key_down(vk: int) -> bool:
    return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)


def is_key_pressed(vk: int) -> bool:
    return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 1)


def read_int(pm, address: int) -> int:
    return pm.read_int(address)


def read_float(pm, address: int) -> float:
    return pm.read_float(address)


def read_ulong64(pm, address: int) -> int:
    return struct.unpack("<Q", pm.read_bytes(address, 8))[0]
