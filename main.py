import fastf1
from datetime import timedelta


class Race:
    def __init__(self, year, rnd, session):
        self.session = fastf1.get_session(year, rnd, session)
        self.session.load(telemetry=True, laps=True)
        self.race_start_time = self._get_race_start_time()
        self.time = 0

    def get_timing_tower(self, detail="leader"):
        timing_data = self._collect_timing_data()
        if not timing_data:
            return []

        timing_data.sort(key=lambda x: x["total_distance"], reverse=True)
        return self._format_timing_tower(timing_data, detail)

    def get_driver_telemetry(self, driver):
        data = self._get_driver_telemetry(driver)
        if data is not None:
            data["speed"] = float(data["speed"])
            data["rpm"] = int(data["rpm"])
            data["gear"] = int(data["gear"])
            data["throttle"] = float(data["throttle"])
            data["brake"] = bool(data["brake"])
            if data["drs"] in [10, 12, 14]:
                data["drs"] = True
            else:
                data["drs"] = False
        return data

    def get_driver_positions(self):
        return self._get_driver_positionings()

    def tick(self, amount=1):
        self.time += amount

    def _collect_timing_data(self):
        timing_data = []
        track_length = self._get_track_length()

        for driver in self.session.drivers:
            driver_data = self._get_driver_info(driver, track_length)
            if driver_data:
                timing_data.append(driver_data)

        return timing_data

    def _get_driver_info(self, driver, track_length):
        session_time = self.race_start_time + timedelta(seconds=self.time)
        driver_laps = self.session.laps.pick_drivers(driver)
        completed_before = driver_laps[driver_laps["Time"] <= session_time]
        in_progress = driver_laps[
            (driver_laps["LapStartTime"] <= session_time)
            & ((driver_laps["Time"] > session_time) | driver_laps["Time"].isna())
        ]

        current_lap, is_complete = self._get_current_lap_info(
            completed_before, in_progress
        )
        if current_lap is None:
            return None

        car_data = current_lap.get_telemetry()
        car_data = car_data[car_data["SessionTime"] <= session_time]
        if car_data.empty:
            return None

        point = car_data.iloc[-1]
        lap_number = current_lap["LapNumber"]

        cumulative_time = self._calculate_cumulative_time(
            completed_before, current_lap, is_complete
        )
        total_distance = (lap_number - 1) * track_length + point["Distance"]

        return {
            "driver": driver,
            "driver_abbr": current_lap["Driver"],
            "lap": lap_number,
            "distance": point["Distance"],
            "total_distance": total_distance,
            "cumulative_time": cumulative_time,
            "compound": current_lap["Compound"],
            "tyre_life": current_lap["TyreLife"],
        }

    def _get_driver_telemetry(self, driver):
        session_time = self.race_start_time + timedelta(seconds=self.time)
        driver_laps = self.session.laps.pick_drivers(driver)
        completed_before = driver_laps[driver_laps["Time"] <= session_time]
        in_progress = driver_laps[
            (driver_laps["LapStartTime"] <= session_time)
            & ((driver_laps["Time"] > session_time) | driver_laps["Time"].isna())
        ]

        current_lap, is_complete = self._get_current_lap_info(
            completed_before, in_progress
        )
        if current_lap is None:
            return None

        car_data = current_lap.get_car_data()
        car_data = car_data[car_data["SessionTime"] <= session_time]
        if car_data.empty:
            return None

        point = car_data.iloc[-1]

        return {
            "driver": driver,
            "driver_abbr": current_lap["Driver"],
            "speed": point["Speed"],
            "rpm": point["RPM"],
            "gear": point["nGear"],
            "throttle": point["Throttle"],
            "brake": point["Brake"],
            "drs": point["DRS"],
        }

    def _get_driver_positionings(self):
        session_time = self.race_start_time + timedelta(seconds=self.time)
        positions = []

        for driver in self.session.drivers:
            driver_laps = self.session.laps.pick_drivers(driver)
            completed_before = driver_laps[driver_laps["Time"] <= session_time]
            in_progress = driver_laps[
                (driver_laps["LapStartTime"] <= session_time)
                & ((driver_laps["Time"] > session_time) | driver_laps["Time"].isna())
            ]

            current_lap, is_complete = self._get_current_lap_info(
                completed_before, in_progress
            )
            if current_lap is None:
                continue

            telemetry = current_lap.get_telemetry()
            telemetry = telemetry[telemetry["SessionTime"] <= session_time]
            if telemetry.empty:
                continue

            point = telemetry.iloc[-1]

            positions.append(
                {
                    "driver": driver,
                    "driver_abbr": current_lap["Driver"],
                    "x": float(point["X"]),
                    "y": float(point["Y"]),
                }
            )

        return positions

    def _get_current_lap_info(self, completed_before, in_progress):
        if in_progress.empty:
            if completed_before.empty:
                return None, False
            return completed_before.iloc[-1], True
        return in_progress.iloc[0], False

    def _calculate_cumulative_time(self, completed_before, current_lap, is_complete):
        session_time = self.race_start_time + timedelta(seconds=self.time)
        cumulative_time = timedelta(0)

        if not completed_before.empty:
            valid_lap_times = completed_before["LapTime"].dropna()
            cumulative_time = valid_lap_times.sum()

        if not is_complete:
            lap_start_time = current_lap["LapStartTime"]
            partial_time = session_time - lap_start_time
            cumulative_time += partial_time

        return cumulative_time

    def _format_timing_tower(self, timing_data, detail):
        track_length = self._get_track_length()
        leader = timing_data[0]
        leader_avg_speed = (
            leader["total_distance"] / leader["cumulative_time"].total_seconds()
            if leader["cumulative_time"].total_seconds() > 0
            else 1
        )

        timing_tower = {
            "lap": int(leader["lap"]),
            "status": self._get_track_status(),
            "positions": [],
        }

        for i, driver in enumerate(timing_data):
            if detail == "leader":
                if i == 0:
                    delta = "Leader"
                else:
                    delta = self._calculate_delta(
                        driver, leader, track_length, leader_avg_speed
                    )
            elif detail == "gap":
                if i == 0:
                    delta = "Gap"
                else:
                    delta = self._calculate_delta(
                        timing_data[i],
                        timing_data[i - 1],
                        track_length,
                        leader_avg_speed,
                    )
            elif detail == "tires":
                delta = self._get_tires(driver)
            else:
                delta = "ERR"

            timing_tower["positions"].append(
                {"position": i + 1, "driver": driver["driver_abbr"], "detail": delta}
            )

        return timing_tower

    def _calculate_delta(self, driver, leader, track_length, leader_avg_speed):
        distance_gap = leader["total_distance"] - driver["total_distance"]
        laps_behind = int(distance_gap / track_length)

        if laps_behind >= 1:
            return f"+{laps_behind} LAP" if laps_behind == 1 else f"+{laps_behind} LAPS"

        time_gap = distance_gap / leader_avg_speed if leader_avg_speed > 0 else 0
        return f"+{abs(time_gap):.3f}s"

    def _get_tires(self, driver):
        compounds = {
            "SOFT": "S",
            "MEDIUM": "M",
            "HARD": "H",
            "INTERMEDIATE": "I",
            "WET": "W",
        }
        compound = compounds.get(driver["compound"], "?")
        life = int(driver["tyre_life"]) if driver["tyre_life"] else 0
        return f"{compound}{life}"

    def _get_track_length(self):
        completed_lap = self.session.laps[self.session.laps["LapTime"].notna()].iloc[0]
        lap_telemetry = completed_lap.get_telemetry()
        return lap_telemetry["Distance"].max()

    def _get_race_start_time(self):
        first_lap = self.session.laps[self.session.laps["LapNumber"] == 1].iloc[0]
        return first_lap["LapStartTime"]

    def _get_current_lap(self, lap):
        laps = self.session.laps
        return laps.pick_laps(lap)

    def _get_track_status(self):
        session_time = self.race_start_time + timedelta(seconds=self.time)
        track_status = self.session.track_status

        status_before = track_status[track_status["Time"] <= session_time]

        if status_before.empty:
            return "Unknown"

        current_status = status_before.iloc[-1]["Status"]

        status_map = {
            "1": "Green",
            "2": "Yellow",
            "4": "SC",
            "5": "Red",
            "6": "VSC",
            "7": "VSC Ending",
        }

        return status_map.get(str(current_status), f"Unknown ({current_status})")


race = Race(2025, 24, "R")

race.tick(145)

print(race.get_timing_tower("gap"))
print("DEBUG", race.get_driver_telemetry("LEC"))
print("DEBUG", race.get_driver_positions())
