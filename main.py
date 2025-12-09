import fastf1
from datetime import timedelta


class Race:
    def __init__(self, year, rnd, session):
        self.session = fastf1.get_session(year, rnd, session)
        self.session.load(telemetry=True, laps=True)

    def get_timing_tower(self, race_time, detail="leader"):
        race_start = self._get_race_start_time()
        session_time = timedelta(seconds=race_start + race_time)

        timing_data = self._collect_timing_data(session_time)
        if not timing_data:
            return []

        timing_data.sort(key=lambda x: x["total_distance"], reverse=True)
        return self._format_timing_tower(timing_data, detail)

    def _collect_timing_data(self, session_time):
        timing_data = []
        track_length = self._get_track_length()

        for driver in self.session.drivers:
            driver_data = self._get_driver_data(driver, session_time, track_length)
            if driver_data:
                timing_data.append(driver_data)

        return timing_data

    def _get_driver_data(self, driver, session_time, track_length):
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

        cumulative_time = self._calculate_cumulative_time(
            completed_before, current_lap, session_time, is_complete
        )

        car_data = current_lap.get_telemetry()
        car_data = car_data[car_data["SessionTime"] <= session_time]
        if car_data.empty:
            return None

        point = car_data.iloc[-1]
        lap_number = current_lap["LapNumber"]
        total_distance = (lap_number - 1) * track_length + point["Distance"]

        compound = current_lap["Compound"]
        tire_life = current_lap["TyreLife"]

        return {
            "driver": driver,
            "driver_abbr": current_lap["Driver"],
            "lap": lap_number,
            "distance": point["Distance"],
            "total_distance": total_distance,
            "cumulative_time": cumulative_time,
            "compound": compound,
            "tyre_life": tire_life,
        }

    def _get_current_lap_info(self, completed_before, in_progress):
        if in_progress.empty:
            if completed_before.empty:
                return None, False
            return completed_before.iloc[-1], True
        return in_progress.iloc[0], False

    def _calculate_cumulative_time(
        self, completed_before, current_lap, session_time, is_complete
    ):
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
        timing_tower = []
        track_length = self._get_track_length()
        leader = timing_data[0]
        leader_avg_speed = (
            leader["total_distance"] / leader["cumulative_time"].total_seconds()
            if leader["cumulative_time"].total_seconds() > 0
            else 1
        )

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

            timing_tower.append(f"{i + 1}. {driver['driver_abbr']} {delta}")

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
        race_start = first_lap["LapStartTime"]
        return race_start.total_seconds()

    def _get_current_lap(self, lap):
        laps = self.session.laps
        return laps.pick_laps(lap)


race = Race(2025, 24, "R")

print(race.get_timing_tower(60, "tires"))
