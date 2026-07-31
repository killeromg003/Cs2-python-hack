import time
from util.core import Offsets, read_int, read_ulong64
from util.entity import get_entity_from_index, resolve_entity_from_handle

def radar(pm, client_base, stop_event):
    
    #Background worker thread that automatically spots players 
    #by writing to their m_bSpotted property in CS2 using util/entity.py functions.
    
    while not stop_event.is_set():
        try:
            entity_list = read_ulong64(pm, client_base + Offsets.dwEntityList)
            if not entity_list:
                time.sleep(1.0)
                continue

            local_player_pawn = read_ulong64(pm, client_base + Offsets.dwLocalPlayerPawn)
            if not local_player_pawn:
                time.sleep(0.5)
                continue

            # Loop through player slot indices (1 to 64)
            for i in range(1, 65):
                entity_controller = get_entity_from_index(pm, entity_list, i)
                if not entity_controller:
                    continue

                try:
                    # Resolve pawn handle from the controller
                    pawn_handle = read_ulong64(pm, entity_controller + Offsets.m_hPlayerPawn)
                    if not pawn_handle:
                        continue

                    entity_pawn = resolve_entity_from_handle(pm, entity_list, pawn_handle)
                    if not entity_pawn or entity_pawn == local_player_pawn:
                        continue

                    # Force the entity to show on the in-game radar minimap
                    pm.write_uchar(entity_pawn + Offsets.m_bSpotted, 1)
                except Exception:
                    continue

        except Exception:
            pass

        # Throttle to roughly ~60 updates per second
        time.sleep(0.016)
