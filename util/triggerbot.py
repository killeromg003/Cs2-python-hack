import time

from util.Entity import get_entity_from_index
from util.core import Buttons, Offsets, VK_F2, VK_XBUTTON1, is_key_down, is_key_pressed, read_int, read_ulong64


def triggerbot(pm, client_base: int, stop_event):
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
