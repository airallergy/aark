import datetime
from typing import TYPE_CHECKING

import pyodbc

if TYPE_CHECKING:
    from collections.abc import Iterable

    type SchedMap = dict[int, dict[str, set[str]]]
    type epJSONObjBody = dict[str, object]
    type epJSONObj = dict[str, epJSONObjBody]


ACTIVITY_SCHED_COLUMN_NAMES = (
    "OCCUPANCY_SCH",
    "LIGHTING_SCH",
    "EQUIPMENT_SCH",
    "COOL_SET_SCH",
    "HEAT_SET_SCH",
    # "OTHER_GAINS_SCH",  # secondary schedule id looked up in [activity_other_gains]
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


def where_in2or(values: Iterable[int], column_name: str) -> str:
    # mdbtools does not support IN (...) after WHERE
    # so use multiple OR clauses instead
    # currently only supports integers
    return " OR ".join(f"[{column_name}] = {item}" for item in values)


def next_month_day(month: int, day: int) -> tuple[int, int]:
    # assuming non-leap year
    date = datetime.date(2026, month, day) + datetime.timedelta(days=1)
    return date.month, date.day


def add_sched_map(
    sched_map: SchedMap, annual_sched_id: int, ep_obj_type: str, ep_obj_name: str
) -> None:
    sched_map.setdefault(annual_sched_id, {})
    sched_map[annual_sched_id].setdefault(ep_obj_type, set())
    sched_map[annual_sched_id][ep_obj_type].add(ep_obj_name)


def add_epjson_obj(
    epjson_objs: epJSONObj, ep_obj_name: str, epjson_obj_body: epJSONObjBody
) -> None:
    if (ep_obj_name in epjson_objs) and (epjson_objs[ep_obj_name] != epjson_obj_body):
        raise ValueError(f"object key collision with different content: {ep_obj_name}")

    epjson_objs.update({ep_obj_name: epjson_obj_body})


def extract_scheds(
    activity_rows: list[pyodbc.Row], cur: pyodbc.Cursor
) -> tuple[SchedMap, epJSONObj]:
    # -----------------------------------------------------------------------------
    # 1) read annual, weekly and daily schedule data
    # -----------------------------------------------------------------------------

    # get annual schedule ids used in the [activity] table
    annual_sched_ids = set(
        getattr(row, column_name)
        for row in activity_rows
        for column_name in ACTIVITY_SCHED_COLUMN_NAMES
    )

    # get annual schedule rows
    query = (
        f"SELECT * FROM [annual_schedules] WHERE {where_in2or(annual_sched_ids, 'ID')}"
    )
    cur.execute(query)
    annual_sched_rows = cur.fetchall()

    # get annual weekly schedule rows
    # note that annual schedules work differently from weekly and daily schedules
    # as they have an indefinite number of segments
    query = f"SELECT * FROM [annual_weekly_schedules] WHERE {where_in2or(annual_sched_ids, 'ANNUAL_SCHEDULE')}"
    cur.execute(query)
    annual_weekly_sched_rows = cur.fetchall()

    # get weekly schedule ids used in the [annual_weekly_schedules] table
    weekly_sched_ids = set(row.WEEKLY_SCHEDULE for row in annual_weekly_sched_rows)

    # get weekly schedule rows
    query = (
        f"SELECT * FROM [weekly_schedules] WHERE {where_in2or(weekly_sched_ids, 'ID')}"
    )
    cur.execute(query)
    weekly_sched_rows = cur.fetchall()

    # get daily schedule ids used in the [weekly_schedules] table
    daily_sched_ids = set(
        getattr(row, day_type)
        for row in weekly_sched_rows
        for day_type in WEEKLY_SCHED_DAY_TYPES
    )

    # get daily schedule rows
    query = (
        f"SELECT * FROM [daily_schedules] WHERE {where_in2or(daily_sched_ids, 'ID')}"
    )
    cur.execute(query)
    daily_sched_rows = cur.fetchall()

    # -----------------------------------------------------------------------------
    # 2) create maps of ids to names
    # -----------------------------------------------------------------------------

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

    # create a map of schedule type ids to names
    query = "SELECT * FROM [schedules_type]"
    cur.execute(query)
    sched_type_id2name = {row.ID: row.COD for row in cur.fetchall()}

    # -----------------------------------------------------------------------------
    # 3) create a map of annual schedule ids to epJSON object names by object type
    # -----------------------------------------------------------------------------

    sched_map = {}

    for annual_sched_row in annual_sched_rows:
        # get and add the annual schedule's ep object name
        # to the `Schedule:Year` set
        annual_sched_id = annual_sched_row.ID
        annual_sched_name = annual_sched_id2name[annual_sched_id]

        add_sched_map(sched_map, annual_sched_id, "Schedule:Year", annual_sched_name)

        # get and add the annual schedule type's ep object name
        annual_sched_type_name = sched_type_id2name[annual_sched_row.TYPE]
        add_sched_map(
            sched_map, annual_sched_id, "ScheduleTypeLimits", annual_sched_type_name
        )

        for annual_weekly_sched_row in annual_weekly_sched_rows:
            if annual_weekly_sched_row.ANNUAL_SCHEDULE != annual_sched_id:
                continue

            # get and add the weekly schedule's ep object name
            # to the `Schedule:Week:Daily` set
            weekly_sched_id = annual_weekly_sched_row.WEEKLY_SCHEDULE
            weekly_sched_name = weekly_sched_id2name[weekly_sched_id]

            add_sched_map(
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

                add_sched_map(
                    sched_map, annual_sched_id, "Schedule:Day:Hourly", daily_sched_name
                )

                # get the daily schedule row coincident with the daily schedule id
                (daily_sched_row,) = (
                    row for row in daily_sched_rows if row.ID == daily_sched_id
                )

                # get and add the daily schedule type's ep object name
                daily_sched_type_name = sched_type_id2name[daily_sched_row.TYPE]
                add_sched_map(
                    sched_map,
                    annual_sched_id,
                    "ScheduleTypeLimits",
                    daily_sched_type_name,
                )

    # -----------------------------------------------------------------------------
    # 4) convert annual, weekly and daily schedules to epJSON objects
    # -----------------------------------------------------------------------------

    epjson_objs = {}

    # add epJSON `ScheduleTypeLimits` objects
    for sched_type_name, epjson_obj_body in SCHED_TYPE_LIMITS_OBJS.items():
        add_epjson_obj(epjson_objs, sched_type_name, epjson_obj_body)

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
                    "sched_week_name": weekly_sched_id2name[
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
                start_month, start_day = next_month_day(
                    sched_weeks[i - 1]["end_month"], sched_weeks[i - 1]["end_day"]
                )
            sched_week["start_month"] = start_month
            sched_week["start_day"] = start_day

        # get schedule type name
        sched_type_name = sched_type_id2name[annual_sched_row.TYPE]

        # create and add the epJSON `Schedule:Year` object
        epjson_obj_body = {
            "sched_type_limits_name": sched_type_name,
            "sched_weeks": sched_weeks,
        }
        add_epjson_obj(epjson_objs, annual_sched_name, epjson_obj_body)

    # convert weekly schedules to epJSON `Schedule:Week:Daily` objects
    for weekly_sched_row in weekly_sched_rows:
        weekly_sched_name = weekly_sched_id2name[weekly_sched_row.ID]

        # create and add the epJSON `Schedule:Week:Daily` object
        epjson_obj_body = {
            f"{day_type.lower()}_sched_day_name": daily_sched_id2name[
                getattr(weekly_sched_row, day_type)
            ]
            for day_type in WEEKLY_SCHED_DAY_TYPES
        }
        # TODO: customday1 and customday2 can probably be safely ignored
        #       but summerdesignday and winterdesignday need a better way to be handled
        fallback_daily_sched_name = epjson_obj_body["holiday_sched_day_name"]
        epjson_obj_body |= {
            "summerdesignday_sched_day_name": fallback_daily_sched_name,
            "winterdesignday_sched_day_name": fallback_daily_sched_name,
            "customday1_sched_day_name": fallback_daily_sched_name,
            "customday2_sched_day_name": fallback_daily_sched_name,
        }
        add_epjson_obj(epjson_objs, weekly_sched_name, epjson_obj_body)

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
        add_epjson_obj(epjson_objs, daily_sched_name, epjson_obj_body)

    return sched_map, epjson_objs
