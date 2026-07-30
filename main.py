"""
CS2 External Triggerbot + Bhop
Reads entity list via 2-level scheme, checks crosshair ID, fires on enemies.

Offsets: Build 14173 (July 29, 2026)
Update offsets from: https://www.cheatoffsets.com/g/cs2  or  cs2-dumper
"""

import pymem
import pymem.process
import time
import ctypes
import threading
import struct
import sys
import requests  # Optional: for auto-updating offsets via API
import json


from util import triggerbot
from util import bunnyhop
from util import Entity





# ================================================================
# CS2 OFFSETS — Build 14173 (2026-07-29)
# Source: cheatoffsets.com + s2v.app schema explorer
# ================================================================
# Read offset 
# Fallback or safely try loading

class Offsets:
    # --- client.dll globals (absolute RVAs from module base) ---
    dwEntityList = data.get("dwEntityList", 0x0)
    dwLocalPlayerPawn     = 0x23A5238   # -> C_CSPlayerPawn (direct)
    dwLocalPlayerController = 0x237FB70 # -> CCSPlayerController
    dwCSGOInput           = 0x23BA790   # -> Input handler (for force commands)
    dwGlobalVars          = 0x2090D60   # Tick count, etc.
    
    # --- Force commands (inside client.dll, pattern-scanned) ---
    # These MUST be updated per build. Get from cs2-dumper or cheatoffsets
    dwForceAttack         = 0x16C1E80   # +attack  (UPDATE THIS!)
    dwForceJump           = 0x16C2390   # +jump    (UPDATE THIS!)

    # --- Entity offsets (from C_CSPlayerPawn / C_BaseEntity) ---
    m_iIDEntIndex         = 0x341C      # Entity index under crosshair
    m_iHealth             = 0x34C       # Health (0 = dead)
    m_iTeamNum            = 0x3EB       # Team: 2=T, 3=CT
    m_lifeState           = 0x350       # 0 = alive, 1 = dead
    m_fFlags              = 0x3F8       # Player flags (bit 0 = on ground)
    m_pGameSceneNode      = 0x330       # -> CGameSceneNode (for position)
    m_vOldOrigin          = 0x15B0      # World position (vec3)
    m_hPawn               = 0x62C       # Pawn handle (from CBasePlayerController)

    # --- Controller offsets (from CCSPlayerController) ---
    m_hPlayerPawn         = 0x90C       # Pawn handle -> get pawn from entity list
    m_iPawnHealth         = 0x918       # Pawn health (on controller)

    # --- Entity list constants ---
    ENT_GROUP_STRIDE      = 0x10        # Stride between entity groups
    ENT_ENTRY_OFFSET      = 0x10        # Offset within group entry to get pointer
    ENT_SLOT_STRIDE       = 0x78        # Stride between entity slots within a group
    MAX_PLAYERS           = 64          # Max players in a match
    
    @classmethod
    def load_from_json(cls, filepath: str) -> None:
        """Reads offset values from a JSON file and sets them on the class."""
        try:
            with open(filepath, "r") as f:
                data = json.load(f)

            for key, val in data.items():
                if hasattr(cls, key):
                    # Convert hex string (e.g. "0x23A5238") to integer if needed
                    if isinstance(val, str) and val.startswith("0x"):
                        val = int(val, 16)

                    setattr(cls, key, val)

            print(f"[+] Offsets successfully loaded from {filepath}")
        except FileNotFoundError:
            print(f"[-] Error: Could not find JSON file at {filepath}")
        except json.JSONDecodeError as e:
            print(f"[-] Error parsing JSON file: {e}")

class Buttons:
    IN_ATTACK    = 1 << 0
    IN_JUMP      = 1 << 1
    IN_DUCK      = 1 << 2
    IN_FORWARD   = 1 << 3
    IN_BACK      = 1 << 4
    IN_USE       = 1 << 5
    IN_LEFT      = 1 << 7
    IN_RIGHT     = 1 << 8
    IN_ATTACK2   = 1 << 11
    IN_SPEED     = 1 << 17
    IN_BULLRUSH  = 1 << 22
    
    # Combined values for force write
    ATTACK_PRESS   = IN_ATTACK | (1 << 16)   # IN_ATTACK | IN_NEW
    ATTACK_RELEASE = (1 << 16)               # IN_NEW only
    JUMP_PRESS     = IN_JUMP | (1 << 16)     # IN_JUMP | IN_NEW
    JUMP_RELEASE   = (1 << 16)               # IN_NEW only



# ================================================================
# VIRTUAL KEY CODES
# ================================================================

VK_SPACE    = 0x20
VK_XBUTTON1 = 0x05   # Mouse side button (back)
VK_XBUTTON2 = 0x06   # Mouse side button (forward)
VK_CAPITAL  = 0x14   # Caps Lock (toggle)
VK_LSHIFT   = 0xA0
VK_LCONTROL = 0xA2
VK_F1       = 0x70
VK_F2       = 0x71
VK_F3       = 0x72
VK_DELETE   = 0x2E


# ================================================================
# HELPER FUNCTIONS
# ================================================================

def is_key_down(vk: int) -> bool:
    """True if key is currently held down."""
    return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)

def is_key_pressed(vk: int) -> bool:
    """True on the frame a key transitions from up→down (for toggles)."""
    return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 1)

def read_uint(pm, addr: int) -> int:
    """Read 4-byte unsigned integer."""
    return pm.read_uint(addr)

def read_int(pm, addr: int) -> int:
    """Read 4-byte signed integer."""
    return pm.read_int(addr)

def read_ulong64(pm, addr: int) -> int:
    """Read 8-byte unsigned long long."""
    return struct.unpack('<Q', pm.read_bytes(addr, 8))[0]

def read_bool(pm, addr: int) -> bool:
    """Read 1 byte as boolean."""
    return pm.read_bytes(addr, 1) != b'\x00'






# ================================================================
# MAIN
# ================================================================

def main():
    # --- Find CS2 process ---
    process_name = "cs2.exe"
    pm = None
    
    try:
        pm = pymem.Pymem(process_name)
    except pymem.exception.ProcessNotFound:
        # Try csgo.exe (some installs still use this)
        try:
            pm = pymem.Pymem("csgo.exe")
            process_name = "csgo.exe"
        except:
            print(f"[-] CS2 process not found. Is the game running?")
            input("Press Enter to exit...")
            return
    except pymem.exception.PymemError as e:
        print(f"[-] Error attaching: {e}")
        input("Press Enter to exit...")
        return
    
    print(f"[+] Attached to {process_name} (PID: {pm.process_id})")
    
    # --- Resolve client.dll ---
    client_module = pymem.process.module_from_name(pm.process_handle, "client.dll")
    if not client_module:
        print("[-] client.dll not found")
        pm.close_process()
        input("Press Enter to exit...")
        return
    
    client_base = client_module.lpBaseOfDll
    print(f"[+] client.dll base: 0x{client_base:X}")
    
    # --- Debug: verify key offsets ---
    print(f"\n[Debug] === Offset Verification ===")
    
    local_pawn = read_ulong64(pm, client_base + Offsets.dwLocalPlayerPawn)
    print(f"  dwLocalPlayerPawn → 0x{local_pawn:X}  {'✓' if local_pawn else '✗ NULL'}")
    
    entity_list = read_ulong64(pm, client_base + Offsets.dwEntityList)
    print(f"  dwEntityList → 0x{entity_list:X}  {'✓' if entity_list else '✗ NULL'}")
    
    if local_pawn:
        try:
            health     = read_int(pm, local_pawn + Offsets.m_iHealth)
            team       = read_int(pm, local_pawn + Offsets.m_iTeamNum)
            crosshair  = read_int(pm, local_pawn + Offsets.m_iIDEntIndex)
            flags      = read_int(pm, local_pawn + Offsets.m_fFlags)
            print(f"  m_iHealth (0x{Offsets.m_iHealth:X}) = {health}")
            print(f"  m_iTeamNum (0x{Offsets.m_iTeamNum:X}) = {team}  {'✓' if team in (2,3) else '?'}")
            print(f"  m_iIDEntIndex (0x{Offsets.m_iIDEntIndex:X}) = {crosshair}")
            print(f"  m_fFlags (0x{Offsets.m_fFlags:X}) = 0x{flags:X}  {'✓' if flags & 1 else '?'}")
        except Exception as e:
            print(f"  ✗ Read error: {e} — offsets may be wrong!")
    
    print("=" * 55)
    
    # --- Ask user to confirm before proceeding ---
    print("\n[!] If offsets look wrong (NULL, 0, or garbage), update them from:")
    print("    https://www.cheatoffsets.com/g/cs2")
    print("    Or run: cs2-dumper (https://github.com/a2x/cs2-dumper)\n")
    
    # --- Start threads ---
    stop_event = threading.Event()
    
    bhop_thread = threading.Thread(
        target=bunnyhop,
        args=(pm, client_base, stop_event),
        daemon=True,
        name="BhopThread"
    )
    
    trigger_thread = threading.Thread(
        target=triggerbot,
        args=(pm, client_base, stop_event),
        daemon=True,
        name="TriggerThread"
    )
    
    bhop_thread.start()
    trigger_thread.start()
    
    print("\n[+] === Controls ===")
    print("    SPACE  = Bunnyhop")
    print("    MButton4 = Triggerbot (side button)")
    print("    F1     = Toggle bhop")
    print("    F2     = Toggle trigger")
    print("    F3     = Exit")
    print("[+] Running. Press F3 to exit.\n")
    
    try:
        while not is_key_down(VK_F3):
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    
    print("\n[+] Shutting down...")
    stop_event.set()
    time.sleep(0.5)
    pm.close_process()
    print("[+] Done. Exiting.")




if __name__ == "__main__":
    main()
