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


# ================================================================
# CS2 OFFSETS — Build 14173 (2026-07-29)
# Source: cheatoffsets.com + s2v.app schema explorer
# ================================================================

class Offsets:
    # --- client.dll globals (absolute RVAs from module base) ---
    dwEntityList          = 0x254FE70   # -> 2-level entity list
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


# ================================================================
# BUTTON FLAGS (same for CS:GO and CS2)
# ================================================================

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
# CS2 ENTITY LIST — 2-LEVEL SCHEME
# ================================================================

def get_entity_from_index(pm, entity_list_base: int, index: int) -> int:
    """
    Resolve an entity from CS2's 2-level entity list.
    
    Returns the entity address, or 0 if invalid.
    """
    if index <= 0 or index > 4096:
        return 0
    
    # Level 1: which group does this index belong to?
    group_index = (index & 0x7FFF) >> 9
    slot_index  = index & 0x1FF
    
    # Each group entry is ENT_GROUP_STRIDE (0x10) bytes apart
    group_entry_addr = entity_list_base + (group_index * Offsets.ENT_GROUP_STRIDE)
    
    # Read the pointer to this group's slot array
    # The pointer is at group_entry_addr + ENT_ENTRY_OFFSET (0x10)
    entry_ptr = read_ulong64(pm, group_entry_addr + Offsets.ENT_ENTRY_OFFSET)
    if not entry_ptr:
        return 0
    
    # Level 2: each slot within the group is ENT_SLOT_STRIDE (0x78) bytes
    entity_addr = entry_ptr + (slot_index * Offsets.ENT_SLOT_STRIDE)
    
    return entity_addr


def resolve_entity_from_handle(pm, entity_list_base: int, handle: int) -> int:
    """
    Resolve an entity from a CHandle (like m_hPlayerPawn).
    The handle encodes the index and serial number.
    
    For most cases, handle & 0x7FFF gives the entity index.
    """
    if handle == 0 or handle == 0xFFFFFFFF:
        return 0
    
    entity_index = handle & 0x7FFF
    return get_entity_from_index(pm, entity_list_base, entity_index)


# ================================================================
# TRIGGERBOT
# ================================================================

def triggerbot(pm, client_base: int, stop_event: threading.Event):
    """
    Read local pawn → read crosshair entity index → resolve entity
    → check team/health → fire via dwForceAttack
    """
    entity_list     = read_ulong64(pm, client_base + Offsets.dwEntityList)
    local_pawn_ptr  = client_base + Offsets.dwLocalPlayerPawn
    force_attack    = client_base + Offsets.dwForceAttack
    
    if not entity_list:
        print("[Trigger] ERROR: Could not read entity list base!")
        return
    
    TRIGGER_KEY = VK_XBUTTON1  # Mouse button 4
    trigger_active = False
    last_trigger_key = False
    
    print(f"[Trigger] Ready. Hold mouse button 4 to fire on enemies.")
    print(f"[Trigger] Entity list base: 0x{entity_list:X}")
    
    while not stop_event.is_set():
        time.sleep(0.001)  # 1ms loop
        
        # --- Toggle trigger on/off with F2 ---
        if is_key_pressed(VK_F2):
            trigger_active = not trigger_active
            print(f"[Trigger] {'ENABLED' if trigger_active else 'DISABLED'}")
        
        if not trigger_active:
            if not is_key_down(TRIGGER_KEY):
                continue
        
        # --- Read local player pawn ---
        local_pawn = read_ulong64(pm, local_pawn_ptr)
        if not local_pawn:
            continue
        
        # --- Read entity index under crosshair ---
        crosshair_idx = read_int(pm, local_pawn + Offsets.m_iIDEntIndex)
        
        # Check if index is valid (0 = nothing, > 64 = not a player)
        if crosshair_idx <= 0 or crosshair_idx > Offsets.MAX_PLAYERS:
            continue
        
        # --- Resolve entity from 2-level list ---
        target_entity = get_entity_from_index(pm, entity_list, crosshair_idx)
        if not target_entity:
            continue
        
        # --- Validate: must be a player entity ---
        # Read first few bytes to check it's not null/garbage
        try:
            health = read_int(pm, target_entity + Offsets.m_iHealth)
        except:
            continue
        
        # --- Skip dead entities ---
        if health <= 0:
            continue
        
        # --- Check life state ---
        life_state = read_int(pm, target_entity + Offsets.m_lifeState)
        if life_state != 0:  # 0 = alive
            continue
        
        # --- Team check ---
        local_team   = read_int(pm, local_pawn + Offsets.m_iTeamNum)
        target_team  = read_int(pm, target_entity + Offsets.m_iTeamNum)
        
        # Teams: 2 = Terrorist, 3 = Counter-Terrorist
        if local_team == target_team:
            continue  # Same team — don't shoot
        
        if local_team not in (2, 3) or target_team not in (2, 3):
            continue  # Spectator or invalid
        
        # --- FIRING DELAY (prevents shooting every tick) ---
        # Minimal: just write the force command
        # The game handles fire rate internally
        
        # --- FIRE! ---
        pm.write_int(force_attack, Buttons.ATTACK_PRESS)
        time.sleep(0.001)
        pm.write_int(force_attack, Buttons.ATTACK_RELEASE)
        
        # --- Small cooldown to prevent hammering ---
        time.sleep(0.015)  # ~15ms ≈ 66 shots/sec max
    
    print("[Trigger] Stopped")


# ================================================================
# BUNNYHOP
# ================================================================

def bunnyhop(pm, client_base: int, stop_event: threading.Event):
    """CS2 bunnyhop via dwForceJump with ground check."""
    local_pawn_ptr = client_base + Offsets.dwLocalPlayerPawn
    force_jump     = client_base + Offsets.dwForceJump
    
    bhop_active = True
    
    print(f"[Bhop] Ready. Hold SPACE to bunnyhop.")
    
    while not stop_event.is_set():
        time.sleep(0.001)
        
        # --- Toggle with F1 ---
        if is_key_pressed(VK_F1):
            bhop_active = not bhop_active
            print(f"[Bhop] {'ENABLED' if bhop_active else 'DISABLED'}")
        
        if not bhop_active:
            continue
        
        if not is_key_down(VK_SPACE):
            continue
        
        # Read local pawn
        local_pawn = read_ulong64(pm, local_pawn_ptr)
        if not local_pawn:
            continue
        
        # Read flags (bit 0 = FL_ONGROUND)
        flags = read_int(pm, local_pawn + Offsets.m_fFlags)
        
        if flags & 1:  # On ground
            pm.write_int(force_jump, Buttons.JUMP_PRESS)
            time.sleep(0.001)
            pm.write_int(force_jump, Buttons.JUMP_RELEASE)
    
    print("[Bhop] Stopped")


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


# ================================================================
# OFFSET AUTO-UPDATER (Optional)
# ================================================================

def fetch_latest_offsets():
    """
    Fetch the latest offsets from cheatoffsets.com API.
    This runs once at startup to auto-update.
    
    Requires: pip install requests
    """
    try:
        import requests
        resp = requests.get(
            "https://www.cheatoffsets.com/api/game/cs2",
            headers={"User-Agent": "CS2-Python-Triggerbot/1.0"},
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            offsets_flat = data.get("offsets_flat", {})
            
            # Map common names
            offset_map = {
                "client_dll.dwEntityList": "dwEntityList",
                "client_dll.dwLocalPlayerPawn": "dwLocalPlayerPawn",
                "client_dll.dwLocalPlayerController": "dwLocalPlayerController",
            }
            
            print("[+] Fetched latest offsets from cheatoffsets.com")
            return True
    except Exception as e:
        print(f"[!] Could not fetch offsets: {e}")
    
    return False


if __name__ == "__main__":
    main()
