import model
import os
import sys
import time


def process_timing_tower(data):
    ret = []
    ret.append("┏━━━━━━━━━━━━━━━━━━━━┓")
    ret.append(f"┃ LAP {data['lap']}{' ' * (20 - len(str(data['lap'])) - 5)}┃")
    ret.append("┠────────────────────┨")
    if data["status"] != "Green":
        ret.append(f"{data['status']}")
        ret.append("┠────────────────────┨")
    for key in data["positions"]:
        data_string = f"{key['driver']}    {key['detail']}"
        ret.append(f"┃ {data_string}{' ' * (20 - len(data_string) - 1)}┃")
    ret.append("┗━━━━━━━━━━━━━━━━━━━━┛")
    return ret


def process_driver_telemetry(data):
    ret = []
    ret.append("┏━━━━┯━━━━━━━━━━━━━┓")
    if data["drs"]:
        drs_string = "[DRS]"
    else:
        drs_string = "     "

    ret.append(
        f"┃ {data['driver']}{' ' * (4 - len(str(data['driver'])) - 1)}│ {data['driver_abbr']}{' ' * (5 - len(data['driver_abbr']))} {drs_string} ┃"
    )
    throttle_string = f"{'┅' * (int(data['throttle'] // 10) % 11)}{' ' * (10 - int(data['throttle'] // 10) % 11)}"
    if data["brake"]:
        brake_string = "┅"
    else:
        brake_string = " "
    ret.append("┠────┴─────────────┨")
    ret.append(f"┃ [{throttle_string}] [{brake_string}] ┃")
    ret.append(f"┃ {data['speed']}{' ' * (18 - len(str(data['speed'])) - 1)}┃")
    ret.append(f"┃ {data['gear']}{' ' * (18 - len(str(data['gear'])) - 1)}┃")
    ret.append(f"┃ {data['rpm']}{' ' * (18 - len(str(data['rpm'])) - 1)}┃")
    ret.append("┗━━━━━━━━━━━━━━━━━━┛")
    return ret


def print_gui(timing_tower, telemetry):
    _clear_screen()

    for i in range(0, len(telemetry)):
        print(f"{timing_tower[i]}{' ' * 4}{telemetry[i]}")

    for j in range(i + 1, len(timing_tower)):
        print(timing_tower[j])


def _clear_screen():
    if os.name == "nt":
        os.system("cls")
    else:
        # Move cursor to home and clear screen
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


race = model.Race(2025, 24, "R")
for i in range(0, 120 * 60):
    race.tick()
    print_gui(
        process_timing_tower(race.get_timing_tower("gap")),
        process_driver_telemetry(race.get_driver_telemetry("LEC")),
    )
    time.sleep(1)
