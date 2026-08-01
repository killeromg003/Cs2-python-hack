import time
from util.core import Offsets, read_int, read_float, read_ulong64
from util.entity import get_entity_from_index, resolve_entity_from_handle

def get_bone_position(pm, entity_pawn: int, bone_index: int = 6) -> tuple:
    try:
        game_scene_node = read_ulong64(pm, entity_pawn + Offsets.m_pGameSceneNode)
        if not game_scene_node:
            return None

        # Read bone array pointer from the model state / skeleton instance
        bone_array_ptr = read_ulong64(pm, game_scene_node + Offsets.m_modelState + 0x80)
        if not bone_array_ptr:
            # Fallback offset variation
            bone_array_ptr = read_ulong64(pm, game_scene_node + Offsets.m_modelState + 0x190)
            if not bone_array_ptr:
                return None

        # Each bone entry is 32 bytes (0x20) apart; coordinates (X, Y, Z) are at the start
        bone_addr = bone_array_ptr + (bone_index * 0x20)
        x = read_float(pm, bone_addr + 0x0)
        y = read_float(pm, bone_addr + 0x4)
        z = read_float(pm, bone_addr + 0x8)

        return (x, y, z)
    except Exception:
        return None
from util.entity import get_all_players
from util.calculation import word_to_screen

def run_esp_logic(pm, client_base, local_player_pawn):
    # Gets all valid players in a single clean pass
    players = get_all_players(pm, client_base, local_player_pawn)
    local_team = read_int(pm, local_player_pawn + Offsets.m_iTeamNum)
    final_viewmatrix = read_int(client_base + Offsets.dwViewAngles)

    for p in players:
        if p["team"] == local_team:
            continue # Skip teammates
            
        
        head_pos = get_bone_position(pm, p["pawn"], 6)
        if head_pos:
            # Do your aim calculations here!
            pass
        head_x,head_y,head_z = head_pos
        world_to_screen(final_viewmatrix,head_x,head_y,head_z)
        


  

             
