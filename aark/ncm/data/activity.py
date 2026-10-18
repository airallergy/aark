"""Read and interpret the NCM activity database."""

from types import MappingProxyType
from typing import TYPE_CHECKING

import aark.ep.sched
from aark._utils import DAY_NAMES, MONTH_ABBRS

if TYPE_CHECKING:
    from typing import Any

    import pyodbc

    from aark._utils import MonthDay

    type DailyScheds = dict[str, tuple[str, ...]]
    type WeeklyScheds = dict[str, dict[str, str]]
    type AnnualScheds = dict[str, tuple[tuple[MonthDay, str], ...]]


DAY_TYPES = (*DAY_NAMES[1:], "Holiday")


def _read_rows(
    table_name: str, cur: pyodbc.Cursor
) -> tuple[MappingProxyType[str, Any], ...]:
    """Read all rows from a database table."""
    # TODO: move to `data._utils` when adding other ncm database readers
    cur.execute(f"SELECT * FROM [{table_name}]")
    col_names = tuple(col[0] for col in cur.description)
    return tuple(
        MappingProxyType(dict(zip(col_names, row, strict=True)))
        for row in cur.fetchall()
    )


def get_sub_val_type(sched_name: str) -> str:
    """Infer a schedule value subtype from an activity schedule name."""
    tokens = sched_name.lower().replace("_", " ").split()

    if ("cool" in tokens) or ("cooling" in tokens):
        return "Cooling"
    elif ("heat" in tokens) or ("heating" in tokens):
        return "Heating"
    else:
        return ""


def _parse_hourly_vals(row: MappingProxyType[str, Any]) -> tuple[str, ...]:
    """Parse 24 hourly values, replacing missing setpoints with an inactive value."""
    sub_val_type = get_sub_val_type(row["NAME"])

    hourly_vals = []
    for i in range(24):
        val = row[f"h{i:02d}"]

        if val is None:
            if not sub_val_type:
                raise NotImplementedError(
                    f"Unsupported missing hourly value: {row['NAME']} h{i:02d}."
                )

            val = aark.ep.sched.get_inactive_val("Temperature", sub_val_type)

        hourly_vals.append(str(val))

    return tuple(hourly_vals)


class _Database:
    """Provide NCM activity data."""

    __slots__ = (
        "_activity_rows",
        "_annual_sched_rows",
        "_annual_weekly_sched_rows",
        "_weekly_sched_rows",
        "_daily_sched_rows",
    )

    _activity_rows: tuple[MappingProxyType[str, Any], ...]
    _annual_sched_rows: tuple[MappingProxyType[str, Any], ...]
    _annual_weekly_sched_rows: tuple[MappingProxyType[str, Any], ...]
    _weekly_sched_rows: tuple[MappingProxyType[str, Any], ...]
    _daily_sched_rows: tuple[MappingProxyType[str, Any], ...]

    def load(self, cur: pyodbc.Cursor) -> None:
        """Load or update data from an NCM database cursor."""
        # read all tables first so a failed read leaves stored data unchanged
        activity_rows = _read_rows("activity", cur)
        annual_sched_rows = _read_rows("annual_schedules", cur)
        annual_weekly_sched_rows = _read_rows("annual_weekly_schedules", cur)
        weekly_sched_rows = _read_rows("weekly_schedules", cur)
        daily_sched_rows = _read_rows("daily_schedules", cur)

        self._activity_rows = activity_rows
        self._annual_sched_rows = annual_sched_rows
        self._annual_weekly_sched_rows = annual_weekly_sched_rows
        self._weekly_sched_rows = weekly_sched_rows
        self._daily_sched_rows = daily_sched_rows

    def _validate_loaded(self) -> None:
        """Validate that the database has been loaded."""
        # `load` assigns all tables after reading succeeds, so one attribute is sufficient
        if not hasattr(self, "_activity_rows"):
            raise RuntimeError(
                f"NCM activity database is not loaded, call `{__package__}.ACTIVITY_DATABASE.load(cur)` first."
            )

    def get_activity_names(self) -> tuple[str, ...]:
        """Get all available activity names."""
        self._validate_loaded()

        return tuple(row["NAME"] for row in self._activity_rows)

    def _get_row(self, activity_name: str) -> MappingProxyType[str, Any]:
        """Get the row for a given activity name."""
        self._validate_loaded()

        (row,) = (row for row in self._activity_rows if row["NAME"] == activity_name)
        return row

    def _get_sched_name(self, annual_sched_uid: int) -> str:
        """Get an annual schedule name."""
        (name,) = (
            row["NAME"]
            for row in self._annual_sched_rows
            if row["ID"] == annual_sched_uid
        )
        return str(name)

    def get_occupancy(self, activity_name: str) -> dict[str, str]:
        """Get occupancy data."""
        row = self._get_row(activity_name)

        return {
            "density": str(row["OCCUPANCY_DENS"]),
            "metabolic_rate": str(row["METABOLIC_RATE"]),
            "sensible_frac": str(1 - row["OCCUP_PERC_LAT"] / 100),
            "sched_name": self._get_sched_name(row["OCCUPANCY_SCH"]),
        }

    def get_lighting(
        self, activity_name: str, luminous_efficacy: float
    ) -> dict[str, str]:
        """Get lighting data."""
        row = self._get_row(activity_name)

        return {
            "power_density": str(float(row["LIGHTING_LUX"]) / luminous_efficacy),
            "sched_name": self._get_sched_name(row["LIGHTING_SCH"]),
        }

    def get_equipment(self, activity_name: str) -> dict[str, str]:
        """Get equipment data."""
        row = self._get_row(activity_name)

        return {
            "power_density": str(row["EQUIPMENT_W_M2"]),
            "latent_frac": str(row["EQUIP_PERC_LAT"] / 100),
            "sched_name": self._get_sched_name(row["EQUIPMENT_SCH"]),
        }

    def get_heating(self, activity_name: str) -> dict[str, str]:
        """Get heating data."""
        row = self._get_row(activity_name)

        setpoint = row["HEAT_SET_POINT"]
        if setpoint is None:
            setpoint = aark.ep.sched.get_inactive_val("Temperature", "Heating")

        return {
            "sched_name": self._get_sched_name(row["HEAT_SET_SCH"]),
            "setpoint": str(setpoint),
        }

    def get_cooling(self, activity_name: str) -> dict[str, str]:
        """Get cooling data."""
        row = self._get_row(activity_name)

        setpoint = row["COOL_SET_POINT"]
        if setpoint is None:
            setpoint = aark.ep.sched.get_inactive_val("Temperature", "Cooling")

        return {
            "sched_name": self._get_sched_name(row["COOL_SET_SCH"]),
            "setpoint": str(setpoint),
        }

    def get_sched(
        self, annual_sched_name: str
    ) -> tuple[DailyScheds, WeeklyScheds, AnnualScheds]:
        """Get daily, weekly and annual profiles for one annual schedule."""
        self._validate_loaded()

        # get annual weekly schedule rows
        (annual_sched_uid,) = (
            row["ID"]
            for row in self._annual_sched_rows
            if row["NAME"] == annual_sched_name
        )
        annual_weekly_sched_rows = tuple(
            row
            for row in self._annual_weekly_sched_rows
            if row["ANNUAL_SCHEDULE"] == annual_sched_uid
        )

        # get weekly schedule rows
        weekly_sched_uids = {row["WEEKLY_SCHEDULE"] for row in annual_weekly_sched_rows}
        weekly_sched_rows = tuple(
            row for row in self._weekly_sched_rows if row["ID"] in weekly_sched_uids
        )

        # get daily schedule rows
        daily_sched_uids = {
            row[day_type.upper()] for row in weekly_sched_rows for day_type in DAY_TYPES
        }
        daily_sched_rows = tuple(
            row for row in self._daily_sched_rows if row["ID"] in daily_sched_uids
        )

        # build daily profiles
        daily_scheds = {}
        daily_sched_uid2name = {}
        for row in daily_sched_rows:
            daily_scheds[row["NAME"]] = _parse_hourly_vals(row)

            daily_sched_uid2name[row["ID"]] = row["NAME"]

        # build weekly profiles
        weekly_scheds = {}
        weekly_sched_uid2name = {}
        for row in weekly_sched_rows:
            weekly_scheds[row["NAME"]] = {
                day_type: daily_sched_uid2name[row[day_type.upper()]]
                for day_type in DAY_TYPES
            }

            weekly_sched_uid2name[row["ID"]] = row["NAME"]

        # build annual profiles
        weekly_sched_endpoints = []
        for row in annual_weekly_sched_rows:
            end_month = MONTH_ABBRS.index(row["END_MONTH"])
            end_day = int(row["END_DAY"])

            weekly_sched_name = weekly_sched_uid2name[row["WEEKLY_SCHEDULE"]]

            weekly_sched_endpoints.append(((end_month, end_day), weekly_sched_name))

        annual_scheds = {annual_sched_name: tuple(weekly_sched_endpoints)}

        return daily_scheds, weekly_scheds, annual_scheds


DATABASE = _Database()
