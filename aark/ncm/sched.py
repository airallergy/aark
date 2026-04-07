"""Convert NCM schedules into epJSON objects.

Caveats:
- a non-leap year is assumed
- other gains schedules are not converted
"""

import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    import pyodbc

    type PyODBCRows = list[pyodbc.Row]
    type PyODBCCursor = pyodbc.Cursor
    type SchedMap = dict[int, dict[str, set[str]]]
    type epJSONObjBody = dict[str, object]  # noqa: N816, PYI042
    type epJSONObjs = dict[str, epJSONObjBody]  # noqa: N816, PYI042


ACTIVITY_SCHED_COLUMN_NAMES = (
    "OCCUPANCY_SCH",
    "LIGHTING_SCH",
    "EQUIPMENT_SCH",
    "COOL_SET_SCH",
    "HEAT_SET_SCH",
    # "OTHER_GAINS_SCH",  # secondary schedule id to look up in [activity_other_gains]
)

WEEKLY_SCHED_DAY_TYPES = (
    "MONDAY",
    "TUESDAY",
    "WEDNESDAY",
    "THURSDAY",
    "FRIDAY",
    "SATURDAY",
    "SUNDAY",
    "HOLIDAY",
)

MONTH_ABBR2NUM = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}

SCHED_TYPE_LIMITS_OBJS = {
    "FRACTION": {
        "lower_limit_value": 0,
        "upper_limit_value": 1,
        "numeric_type": "Continuous",
        "unit_type": "Dimensionless",
    },
    "ON/OFF": {
        "lower_limit_value": 0,
        "upper_limit_value": 1,
        "numeric_type": "Discrete",
        "unit_type": "Availability",
    },
    "TEMPERATURE": {
        "lower_limit_value": -100,
        "upper_limit_value": 100,
        "numeric_type": "Continuous",
        "unit_type": "Temperature",
    },
}


def _fetch_filter(
    table_name: str,
    column_name: str,
    column_values: Iterable[object],
    cursor: PyODBCCursor,
) -> PyODBCRows:
    """Fetch rows of a table filtered by values in a given column.

    NOTE: this fetch and filter approach is used instead of a SQL query with a WHERE
    clause, because some ODBC driver apears to have a limit on the number of column
    values to be filtered via WHERE.
    """
    column_values = set(column_values)

    cursor.execute(f"SELECT * FROM [{table_name}]")
    rows = cursor.fetchall()
    return [row for row in rows if getattr(row, column_name) in column_values]


def _next_month_day(month: int, day: int) -> tuple[int, int]:
    """Return the next month and day given a month and day.

    NOTE: this function hardcodes a non-leap year.
    """
    date = datetime.date(2026, month, day) + datetime.timedelta(days=1)
    return date.month, date.day


def _add_sched_map(
    sched_map: SchedMap, annual_sched_id: int, ep_obj_type: str, ep_obj_name: str
) -> None:
    """Add mapping to an epJSON object name by annual schedule id and EP object type."""
    sched_map.setdefault(annual_sched_id, {})
    sched_map[annual_sched_id].setdefault(ep_obj_type, set())
    sched_map[annual_sched_id][ep_obj_type].add(ep_obj_name)


def _add_epjson_obj(
    epjson_objs: epJSONObjs, ep_obj_name: str, epjson_obj_body: epJSONObjBody
) -> None:
    """Add an epJSON object."""
    if (ep_obj_name in epjson_objs) and (epjson_objs[ep_obj_name] != epjson_obj_body):
        raise ValueError(f"object key collision with different content: {ep_obj_name}")

    epjson_objs.update({ep_obj_name: epjson_obj_body})


def read_scheds(
    activity_rows: PyODBCRows, cursor: PyODBCCursor
) -> tuple[PyODBCRows, PyODBCRows, PyODBCRows, PyODBCRows, PyODBCRows]:
    """Read NCM activity schedule data.

    Parameters
    ----------
    activity_rows : PyODBCRows
        Rows of the `[activity]` table.
    cursor : PyODBCCursor
        Open cursor of the NCM activity database.

    Returns
    -------
    tuple[PyODBCRows, PyODBCRows, PyODBCRows, PyODBCRows, PyODBCRows]
        A tuple containing:
        - rows of the `[annual_schedules]` table.
        - rows of the `[annual_weekly_schedules]` table.
        - rows of the `[weekly_schedules]` table.
        - rows of the `[daily_schedules]` table.
        - rows of the `[schedules_type]` table.
    """
    # get schedule type rows
    cursor.execute("SELECT * FROM [schedules_type]")
    sched_type_rows = cursor.fetchall()

    # get annual schedule ids used in the [activity] table
    annual_sched_ids = {
        getattr(row, column_name)
        for row in activity_rows
        for column_name in ACTIVITY_SCHED_COLUMN_NAMES
    }

    # get annual schedule rows
    annual_sched_rows = _fetch_filter(
        "annual_schedules", "ID", annual_sched_ids, cursor
    )

    # get annual weekly schedule rows
    # note that annual schedules work differently from weekly and daily schedules
    # as they have an indefinite number of segments
    annual_weekly_sched_rows = _fetch_filter(
        "annual_weekly_schedules", "ANNUAL_SCHEDULE", annual_sched_ids, cursor
    )

    # get weekly schedule ids used in the [annual_weekly_schedules] table
    weekly_sched_ids = {row.WEEKLY_SCHEDULE for row in annual_weekly_sched_rows}

    # get weekly schedule rows
    weekly_sched_rows = _fetch_filter(
        "weekly_schedules", "ID", weekly_sched_ids, cursor
    )

    # get daily schedule ids used in the [weekly_schedules] table
    daily_sched_ids = {
        getattr(row, day_type)
        for row in weekly_sched_rows
        for day_type in WEEKLY_SCHED_DAY_TYPES
    }

    # get daily schedule rows
    daily_sched_rows = _fetch_filter("daily_schedules", "ID", daily_sched_ids, cursor)

    return (
        annual_sched_rows,
        annual_weekly_sched_rows,
        weekly_sched_rows,
        daily_sched_rows,
        sched_type_rows,
    )


def convert_scheds(  # noqa: PLR0915
    annual_sched_rows: PyODBCRows,
    annual_weekly_sched_rows: PyODBCRows,
    weekly_sched_rows: PyODBCRows,
    daily_sched_rows: PyODBCRows,
    sched_type_rows: PyODBCRows,
) -> tuple[SchedMap, epJSONObjs]:
    """Convert NCM schedule data into an epJSON schedule library.

    Parameters
    ----------
    annual_sched_rows : PyODBCRows
        Rows of the `[annual_schedules]` table.
    annual_weekly_sched_rows : PyODBCRows
        Rows of the `[annual_weekly_schedules]` table.
    weekly_sched_rows : PyODBCRows
        Rows of the `[weekly_schedules]` table.
    daily_sched_rows : PyODBCRows
        Rows of the `[daily_schedules]` table.
    sched_type_rows : PyODBCRows
        Rows of the `[schedules_type]` table.

    Returns
    -------
    tuple[SchedMap, epJSONObjs]
        An epJSON schedule library containing:
        - a map of annual schedule ids to epJSON object names grouped by EP object type.
        - a map of epJSON object names to epJSON object bodies.
    """
    # -----------------------------------------------------------------------------
    # 1) create maps of ids to names
    # -----------------------------------------------------------------------------

    # create a map of schedule type ids to names
    sched_type_id2name = {row.ID: row.COD for row in sched_type_rows}

    # create a map of ncm ids to ep object names for annual schedules
    annual_sched_id2name = {
        row.ID: f"ncm-annual-{row.ID}-{row.NAME}" for row in annual_sched_rows
    }

    # create a map of ncm ids to ep object names for weekly schedules
    weekly_sched_id2name = {
        row.ID: f"ncm-weekly-{row.ID}-{row.NAME}" for row in weekly_sched_rows
    }

    # create a map of ncm ids to ep object names for daily schedules
    daily_sched_id2name = {
        row.ID: f"ncm-daily-{row.ID}-{row.NAME}" for row in daily_sched_rows
    }

    # -----------------------------------------------------------------------------
    # 2) create a map of annual schedule ids to epJSON object names by object type
    # -----------------------------------------------------------------------------

    sched_map: SchedMap = {}

    for annual_sched_row in annual_sched_rows:
        # get and add the annual schedule's ep object name
        # to the `Schedule:Year` set
        annual_sched_id = annual_sched_row.ID
        annual_sched_name = annual_sched_id2name[annual_sched_id]

        _add_sched_map(sched_map, annual_sched_id, "Schedule:Year", annual_sched_name)

        # get and add the annual schedule type's ep object name
        annual_sched_type_name = sched_type_id2name[annual_sched_row.TYPE]
        _add_sched_map(
            sched_map, annual_sched_id, "ScheduleTypeLimits", annual_sched_type_name
        )

        for annual_weekly_sched_row in annual_weekly_sched_rows:
            if annual_weekly_sched_row.ANNUAL_SCHEDULE != annual_sched_id:
                continue

            # get and add the weekly schedule's ep object name
            # to the `Schedule:Week:Daily` set
            weekly_sched_id = annual_weekly_sched_row.WEEKLY_SCHEDULE
            weekly_sched_name = weekly_sched_id2name[weekly_sched_id]

            _add_sched_map(
                sched_map, annual_sched_id, "Schedule:Week:Daily", weekly_sched_name
            )

            # get the weekly schedule row coincident with the weekly schedule id
            (weekly_sched_row,) = (
                row for row in weekly_sched_rows if row.ID == weekly_sched_id
            )

            for day_type in WEEKLY_SCHED_DAY_TYPES:
                # get and add the daily schedule's ep object name
                # to the `Schedule:Day:Hourly` set
                daily_sched_id = getattr(weekly_sched_row, day_type)
                daily_sched_name = daily_sched_id2name[daily_sched_id]

                _add_sched_map(
                    sched_map, annual_sched_id, "Schedule:Day:Hourly", daily_sched_name
                )

                # get the daily schedule row coincident with the daily schedule id
                (daily_sched_row,) = (
                    row for row in daily_sched_rows if row.ID == daily_sched_id
                )

                # get and add the daily schedule type's ep object name
                daily_sched_type_name = sched_type_id2name[daily_sched_row.TYPE]
                _add_sched_map(
                    sched_map,
                    annual_sched_id,
                    "ScheduleTypeLimits",
                    daily_sched_type_name,
                )

    # -----------------------------------------------------------------------------
    # 3) convert annual, weekly and daily schedules to epJSON objects
    # -----------------------------------------------------------------------------

    epjson_objs: epJSONObjs = {}

    # add epJSON `ScheduleTypeLimits` objects
    for sched_type_name, epjson_obj_body in SCHED_TYPE_LIMITS_OBJS.items():
        _add_epjson_obj(epjson_objs, sched_type_name, epjson_obj_body)

    # convert annual schedules to epJSON `Schedule:Year` objects
    for annual_sched_row in annual_sched_rows:
        annual_sched_id = annual_sched_row.ID
        annual_sched_name = annual_sched_id2name[annual_sched_id]

        # create the list of schedule weeks given the annual schedule
        # add placeholders for start month and start day
        # sort the schedule weeks by end month and end day
        sched_weeks = []

        for annual_weekly_sched_row in annual_weekly_sched_rows:
            if annual_weekly_sched_row.ANNUAL_SCHEDULE != annual_sched_id:
                continue

            sched_weeks.append(
                {
                    "schedule_week_name": weekly_sched_id2name[
                        annual_weekly_sched_row.WEEKLY_SCHEDULE
                    ],
                    "start_month": -1,
                    "start_day": -1,
                    "end_month": MONTH_ABBR2NUM[annual_weekly_sched_row.END_MONTH],
                    "end_day": int(annual_weekly_sched_row.END_DAY),
                }
            )

        sched_weeks.sort(key=lambda x: (x["end_month"], x["end_day"]))

        # check that the last end month and end day are 12 and 31
        assert sched_weeks[-1]["end_month"] == 12
        assert sched_weeks[-1]["end_day"] == 31

        # update start month and start day for each schedule week
        # based on the end month and end day of the previous schedule week
        for i, sched_week in enumerate(sched_weeks):
            if i == 0:
                start_month, start_day = 1, 1
            else:
                start_month, start_day = _next_month_day(
                    sched_weeks[i - 1]["end_month"],  # type: ignore[arg-type]
                    sched_weeks[i - 1]["end_day"],  # type: ignore[arg-type]
                )
            sched_week["start_month"] = start_month
            sched_week["start_day"] = start_day

        # get schedule type name
        sched_type_name = sched_type_id2name[annual_sched_row.TYPE]

        # create and add the epJSON `Schedule:Year` object
        epjson_obj_body = {
            "schedule_type_limits_name": sched_type_name,
            "schedule_weeks": sched_weeks,
        }
        _add_epjson_obj(epjson_objs, annual_sched_name, epjson_obj_body)

    # convert weekly schedules to epJSON `Schedule:Week:Daily` objects
    for weekly_sched_row in weekly_sched_rows:
        weekly_sched_name = weekly_sched_id2name[weekly_sched_row.ID]

        # create and add the epJSON `Schedule:Week:Daily` object
        epjson_obj_body = {
            f"{day_type.lower()}_schedule_day_name": daily_sched_id2name[
                getattr(weekly_sched_row, day_type)
            ]
            for day_type in WEEKLY_SCHED_DAY_TYPES
        }
        # TODO: customday1 and customday2 can probably be safely ignored
        #       but summerdesignday and winterdesignday need a better way to be handled
        fallback_daily_sched_name = epjson_obj_body["holiday_schedule_day_name"]
        epjson_obj_body |= {
            "summerdesignday_schedule_day_name": fallback_daily_sched_name,
            "winterdesignday_schedule_day_name": fallback_daily_sched_name,
            "customday1_schedule_day_name": fallback_daily_sched_name,
            "customday2_schedule_day_name": fallback_daily_sched_name,
        }
        _add_epjson_obj(epjson_objs, weekly_sched_name, epjson_obj_body)

    # convert daily schedules to epJSON `Schedule:Day:Hourly` objects
    for daily_sched_row in daily_sched_rows:
        daily_sched_name = daily_sched_id2name[daily_sched_row.ID]

        # get schedule type name
        sched_type_name = sched_type_id2name[daily_sched_row.TYPE]

        # create and add the epJSON `Schedule:Day:Hourly` object
        epjson_obj_body = {"sched_type_limits_name": sched_type_name}
        epjson_obj_body |= {
            f"hour_{i + 1}": getattr(daily_sched_row, f"h{i:02d}") for i in range(24)
        }
        _add_epjson_obj(epjson_objs, daily_sched_name, epjson_obj_body)

    return sched_map, epjson_objs


def pick_scheds(
    room_names: Sequence[str],
    sched_categories: Sequence[str],
    sched_map: SchedMap,
    epjson_objs: epJSONObjs,
    activity_rows: PyODBCRows,
) -> dict[str, epJSONObjs]:
    """Pick epJSON schedule objects given rooms and schedule categories.

    Parameters
    ----------
    room_names : Sequence[str]
        NCM room names of interest.
    sched_categories : Sequence[str]
        NCM schedule categories of interest.
    sched_map : SchedMap
        Map of annual schedule ids to epJSON object names grouped by EP object type.
    epjson_objs : epJSONObjs
        Map of epJSON object names to epJSON object bodies.
    activity_rows : PyODBCRows
        Rows of the `[activity]` table.

    Returns
    -------
    dict[str, epJSONObjs]
        An epJSON of schedules.
    """
    annual_sched_ids = {
        getattr(row, column_name)
        for row in activity_rows
        if row.NAME in room_names
        for column_name in sched_categories
    }

    sched_epjson: dict[str, epJSONObjs] = {
        "ScheduleTypeLimits": {},
        "Schedule:Day:Hourly": {},
        "Schedule:Week:Daily": {},
        "Schedule:Year": {},
    }

    for annual_sched_id in annual_sched_ids:
        for ep_obj_type, ep_obj_names in sched_map[annual_sched_id].items():
            for ep_obj_name in sorted(ep_obj_names):
                sched_epjson[ep_obj_type][ep_obj_name] = epjson_objs[ep_obj_name]

    return sched_epjson


def get_scheds(
    room_names: Sequence[str], sched_categories: Sequence[str], cursor: PyODBCCursor
) -> dict[str, epJSONObjs]:
    """Get an epJSON of schedules given rooms and schedule categories.

    This is a helper function that streamlines `read_scheds`, `convert_scheds` and
    `pick_scheds` into a single function call.

    Parameters
    ----------
    room_names : Sequence[str]
        NCM room names of interest.
    sched_categories : Sequence[str]
        NCM schedule category column names of interest.
    cursor : PyODBCCursor
        Open cursor of the NCM activity database.

    Returns
    -------
    dict[str, epJSONObjs]
        An epJSON of schedules.
    """
    # get activity rows
    activity_rows = _fetch_filter("activity", "NAME", room_names, cursor)

    # read NCM schedule data
    (
        annual_sched_rows,
        annual_weekly_sched_rows,
        weekly_sched_rows,
        daily_sched_rows,
        sched_type_rows,
    ) = read_scheds(activity_rows, cursor)

    # convert NCM schedule data into an epJSON schedule library
    sched_map, epjson_objs = convert_scheds(
        annual_sched_rows,
        annual_weekly_sched_rows,
        weekly_sched_rows,
        daily_sched_rows,
        sched_type_rows,
    )

    # pick epJSON schedule objects given rooms and schedule categories
    return pick_scheds(
        room_names, sched_categories, sched_map, epjson_objs, activity_rows
    )
