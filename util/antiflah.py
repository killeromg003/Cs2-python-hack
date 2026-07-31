def antiflash(pm, client_base: int, stop_event, offsets, interval: float = 0.01):

    required_offsets = ("dwLocalPlayerPawn", "m_FlashBangTime")
    missing = [name for name in required_offsets if not hasattr(offsets, name)]
    if missing:
        raise ValueError(f"[AntiFlash] Missing required offsets: {', '.join(missing)}")

    local_pawn_address = client_base + offsets.dwLocalPlayerPawn
    flash_offset = offsets.m_FlashBangTime

    if not flash_offset:
        raise ValueError("[AntiFlash] m_FlashBangTime is 0; update offsets.json first.")

    print("[AntiFlash] Ready. Flash duration will be cleared while running.")

    while not stop_event.is_set():
        try:
            local_pawn = _read_pointer(pm, local_pawn_address)
            if local_pawn:
                flash_time_address = local_pawn + flash_offset
                flash_time = pm.read_float(flash_time_address)
                if flash_time == 0.0:
                    break
                else:
                    pm.write_float(flash_time_address, 0.0)
        except Exception as error:
            print(f"[AntiFlash] Read/write skipped: {error}")

        time.sleep(interval)

    print("[AntiFlash] Stopped")

