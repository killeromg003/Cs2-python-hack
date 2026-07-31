import threading
import time

import pymem
import pymem.process

from util.antiflash import antiflash
from util.bunnyhop import bunnyhop
from util.core import Offsets, VK_F3, VK_F4, is_key_down, is_key_pressed, read_int, read_ulong64
from util.triggerbot import triggerbot


def main():
    if not Offsets.load_from_json("offset.json"):
        return

    process_name = "cs2.exe"
    try:
        pm = pymem.Pymem(process_name)
    except pymem.exception.ProcessNotFound:
        try:
            pm = pymem.Pymem("csgo.exe")
            process_name = "csgo.exe"
        except pymem.exception.PymemError:
            print("[-] CS2 process not found. Is the game running?")
            return
    except pymem.exception.PymemError as error:
        print(f"[-] Could not attach to CS2: {error}")
        return

    try:
        print(f"[+] Attached to {process_name} (PID: {pm.process_id})")
        client_module = pymem.process.module_from_name(pm.process_handle, "client.dll")
        if not client_module:
            print("[-] client.dll not found")
            return

        client_base = client_module.lpBaseOfDll
        print(f"[+] client.dll base: 0x{client_base:X}")

        try:
            local_pawn = read_ulong64(pm, client_base + Offsets.dwLocalPlayerPawn)
            entity_list = read_ulong64(pm, client_base + Offsets.dwEntityList)
            print("\n[Debug] === Offset Verification ===")
            print(f"  dwLocalPlayerPawn -> 0x{local_pawn:X}")
            print(f"  dwEntityList -> 0x{entity_list:X}")
            if local_pawn:
                health = read_int(pm, local_pawn + Offsets.m_iHealth)
                team = read_int(pm, local_pawn + Offsets.m_iTeamNum)
                print(f"  m_iHealth = {health}")
                print(f"  m_iTeamNum = {team}")
        except Exception as error:
            print(f"[!] Offset verification failed: {error}")

        stop_event = threading.Event()
        antiflash_enabled = threading.Event()
        workers = (
            threading.Thread(target=bunnyhop, args=(pm, client_base, stop_event), daemon=True, name="BhopThread"),
            threading.Thread(target=triggerbot, args=(pm, client_base, stop_event), daemon=True, name="TriggerThread"),
            threading.Thread(
                target=antiflash,
                args=(pm, client_base, stop_event, antiflash_enabled, Offsets),
                daemon=True,
                name="AntiFlashThread",
            ),
        )
        for worker in workers:
            worker.start()

        print("\n[+] === Controls ===")
        print("    SPACE    = Bunnyhop")
        print("    MButton4 = Triggerbot (hold)")
        print("    F1       = Toggle bhop")
        print("    F2       = Toggle trigger")
        print("    F3       = Exit")
        print("    F4       = Toggle AntiFlash (default: OFF)\n")

        try:
            while not is_key_down(VK_F3):
                if is_key_pressed(VK_F4):
                    if antiflash_enabled.is_set():
                        antiflash_enabled.clear()
                        print("[AntiFlash] DISABLED")
                    else:
                        antiflash_enabled.set()
                        print("[AntiFlash] ENABLED")
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            print("[+] Shutting down...")
            stop_event.set()
            for worker in workers:
                worker.join(timeout=1.0)
    finally:
        pm.close_process()
        print("[+] Done. Exiting.")


if __name__ == "__main__":
    main()
