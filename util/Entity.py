from util.core import Offsets, read_ulong64

def get_entity_from_index(pm, entity_list_base: int, index: int) -> int:
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
    
    # Level 2: each slot contains a pointer to an entity.
    entity_slot_addr = entry_ptr + (slot_index * Offsets.ENT_SLOT_STRIDE)
    return read_ulong64(pm, entity_slot_addr)


def resolve_entity_from_handle(pm, entity_list_base: int, handle: int) -> int:
    if handle == 0 or handle == 0xFFFFFFFF:
        return 0
    
    entity_index = handle & 0x7FFF
    return get_entity_from_index(pm, entity_list_base, entity_index)
# In util/entity.py

def get_all_players(pm, client_base, local_player_pawn):
    """
    Scans the entity list once and returns a list of dictionaries 
    containing valid player info (controller, pawn, team, health).
    """
    entity_list = read_ulong64(pm, client_base + Offsets.dwEntityList)
    if not entity_list:
        return []

    players = []
    local_team = read_int(pm, local_player_pawn + Offsets.m_iTeamNum) if local_player_pawn else 0

    for i in range(1, 65):
        entity_controller = get_entity_from_index(pm, entity_list, i)
        if not entity_controller:
            continue

        pawn_handle = read_ulong64(pm, entity_controller + Offsets.m_hPlayerPawn)
        if not pawn_handle:
            continue

        entity_pawn = resolve_entity_from_handle(pm, entity_list, pawn_handle)
        if not entity_pawn or entity_pawn == local_player_pawn:
            continue

        health = read_int(pm, entity_pawn + Offsets.m_iHealth)
        if health <= 0 or health > 100:
            continue

        team = read_int(pm, entity_pawn + Offsets.m_iTeamNum)

        players.append({
            "index": i,
            "controller": entity_controller,
            "pawn": entity_pawn,
            "team": team,
            "health": health
        })

    return players
