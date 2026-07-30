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

