import time

from util.core import Buttons, Offsets, VK_F1, VK_SPACE, is_key_down, is_key_pressed, read_int, read_ulong64


def bunnyhop(pm, client_base: int, stop_event):
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
