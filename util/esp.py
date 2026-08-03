import struct
import time

from util.calculation import world_to_screen
from util.core import Offsets, read_float, read_int, read_ulong64
from util.entity import get_all_players


def get_bone_position(pm, entity_pawn: int, bone_index: int = 6):
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


def run_esp_logic(pm, client_base, stop_event, local_player_pawn):
    print("[ESP] Ready.")

    while not stop_event.is_set():
        time.sleep(0.001)

        players = get_all_players(pm, client_base, local_player_pawn)
        local_team = read_int(pm, local_player_pawn + Offsets.m_iTeamNum)

        # dwViewMatrix points to a 4x4 float matrix (16 floats, 64 bytes)
        view_matrix_ptr = read_ulong64(pm, client_base + Offsets.dwViewMatrix)
        if not view_matrix_ptr:
            continue

        matrix = struct.unpack("<16f", pm.read_bytes(view_matrix_ptr, 64))

        for p in players:
            if p["team"] == local_team:
                continue  # Skip teammates

            head_pos = get_bone_position(pm, p["pawn"], 6)
            if not head_pos:
                continue

            screen = world_to_screen(matrix, *head_pos)
            if screen is None:
                continue

            # Rendering/overlay is not implemented here; screen coords are ready to draw.
            pass
