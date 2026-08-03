import math

from util.core import Offsets, read_float, read_ulong64
from util.esp import get_bone_position


def calculate_angles(local_pos, target_pos):
    delta_x = target_pos[0] - local_pos[0]
    delta_y = target_pos[1] - local_pos[1]
    delta_z = target_pos[2] - local_pos[2]

    # Calculate hypotenuse in 2D plane (X and Y)
    hypotenuse = math.hypot(delta_x, delta_y)

    # Pitch: vertical angle (looking up/down)
    # Note: In Source engine, pitch is inverted (-degrees)
    pitch = -math.degrees(math.atan2(delta_z, hypotenuse))

    # Yaw: horizontal angle (looking left/right)
    yaw = math.degrees(math.atan2(delta_y, delta_x))

    # Normalize angles to standard game bounds
    # Pitch: -89.0 to 89.0, Yaw: -180.0 to 180.0
    pitch = max(-89.0, min(89.0, pitch))
    yaw = (yaw + 180.0) % 360.0 - 180.0

    return pitch, yaw


def aimbot(pm, client_base, local_player_pawn, target_pawn):
    """Aim the local player's view angles at the target pawn's head."""
    if not local_player_pawn or not target_pawn:
        return False

    # Read local player eye position (origin + view offset)
    origin_x = read_float(pm, local_player_pawn + Offsets.m_vOldOrigin)
    origin_y = read_float(pm, local_player_pawn + Offsets.m_vOldOrigin + 0x4)
    origin_z = read_float(pm, local_player_pawn + Offsets.m_vOldOrigin + 0x8)

    view_offset_z = read_float(pm, local_player_pawn + Offsets.m_vecViewOffset + 0x8)
    local_eye_pos = (origin_x, origin_y, origin_z + view_offset_z)

    head_pos = get_bone_position(pm, target_pawn, 6)
    if not head_pos:
        return False

    pitch, yaw = calculate_angles(local_eye_pos, head_pos)

    # Write to client view angles
    # View angles usually consist of [pitch, yaw, roll (always 0)]
    view_angles_base = read_ulong64(pm, client_base + Offsets.dwViewAngles)
    if not view_angles_base:
        return False

    pm.write_float(view_angles_base + 0x0, pitch)
    pm.write_float(view_angles_base + 0x4, yaw)
    return True
