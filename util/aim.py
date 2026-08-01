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

def run_aimbot_logic(pm, client_base):
    """Main loop combining steps 1, 2, and 3 for target tracking."""
    entity_list = read_ulong64(pm, client_base + Offsets.dwEntityList)
    local_player_pawn = read_ulong64(pm, client_base + Offsets.dwLocalPlayerPawn)
    final_viewmatrix = read_int(Offsets.dwViewMatrix + client_base)
    
    if not entity_list or not local_player_pawn:
        return

    local_team = read_int(pm, local_player_pawn + Offsets.m_iTeamNum)

    # Step 1: Iterate through player list indices (1 to 64)
    for i in range(1, 65):
        entity_controller = get_entity_from_index(pm, entity_list, i)
        if not entity_controller:
        	continue

        # Resolve player pawn from controller handle
        pawn_handle = read_ulong64(pm, entity_controller + Offsets.m_hPlayerPawn)
        if not pawn_handle:
            continue

        entity_pawn = resolve_entity_from_handle(pm, entity_list, pawn_handle)
        if not entity_pawn or entity_pawn == local_player_pawn:
            continue

        # Step 2: Read Player Properties (Health, Team, Dead state)
        health = read_int(pm, entity_pawn + Offsets.m_iHealth)
        team = read_int(pm, entity_pawn + Offsets.m_iTeamNum)

        # Skip dead players or teammates
        if health <= 0 or health > 100 or team == local_team:
            continue

        # Step 3: Read Bone Positions (Head position at index 6)
        head_pos = get_bone_position(pm, entity_pawn, 6)
        if not head_pos:
            continue

        head_x, head_y, head_z = head_pos
        world_to_screen(final_viewmatrix, 