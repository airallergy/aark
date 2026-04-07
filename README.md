# `aark`

airallergy’s research kit

`aark` is a collection of Python tools for my research in built environment.

**Table of contents**

- [Usage](#usage)
  - [NCM](#ncm)
    - [Get activity schedules in the epJSON format](#get-activity-schedules-in-the-epjson-format)

## Usage

### NCM

Tools for analysing the [National Calculation Methodology (NCM) database](https://www.uk-ncm.org.uk/), tested primarily on data related to English dwellings.

> [!TIP]
> To access the NCM database, the NCM modules depend on `pyodbc`, which in turn depends on an ODBC driver and driver manager for Microsoft Access. See [`pyodbc`'s installation guide](https://github.com/mkleehammer/pyodbc/wiki/Install) for details.

#### Get activity schedules in the epJSON format

The `aark.ncm.sched` module provides functions for extracting NCM activity schedules and converting them into the epJSON format for EnergyPlus. In particular, the `aark.ncm.sched.get_scheds` function takes a sequence of NCM room names, a sequence of NCM schedule categories and a `pyodbc.Cursor` object for the NCM activity database, and returns an epJSON of schedule objects ready for EnergyPlus simulations.

> [!IMPORTANT]
> This module currently has the following caveats:
>
> - A non-leap year is assumed.
> - Other gains schedules are not converted.

For instance, the following script retrieves the occupancy and heating set point schedules for the bedroom and the lounge.

```python
import pyodbc

import aark.ncm.sched


room_names = ["Dwell_DomBed", "Dwell_DomLounge"]
sched_categories = ["OCCUPANCY_SCH", "HEAT_SET_SCH"]

with pyodbc.connect(
    Driver="Microsoft Access Driver (*.mdb, *.accdb)", DBQ="/path/to/the/database"
) as con:
    cur = con.cursor()

    sched_epjson = aark.ncm.sched.get_scheds(
        room_names=room_names, sched_categories=sched_categories, cursor=cur
    )
```

The `sched_epjson` variable contains the following epJSON of schedule objects.

<details>
<summary>Full epJSON</summary>

```json
{
  "ScheduleTypeLimits": {
    "TEMPERATURE": {
      "lower_limit_value": -100,
      "upper_limit_value": 100,
      "numeric_type": "Continuous",
      "unit_type": "Temperature"
    },
    "FRACTION": {
      "lower_limit_value": 0,
      "upper_limit_value": 1,
      "numeric_type": "Continuous",
      "unit_type": "Dimensionless"
    }
  },
  "Schedule:Day:Hourly": {
    "ncm-daily-9344-Dwell_DomBed_Heat_Wkdy": {
      "sched_type_limits_name": "TEMPERATURE",
      "hour_1": 18,
      "hour_2": 18,
      "hour_3": 18,
      "hour_4": 18,
      "hour_5": 18,
      "hour_6": 18,
      "hour_7": 18,
      "hour_8": 18,
      "hour_9": 18,
      "hour_10": 12,
      "hour_11": 12,
      "hour_12": 12,
      "hour_13": 12,
      "hour_14": 12,
      "hour_15": 12,
      "hour_16": 12,
      "hour_17": 12,
      "hour_18": 12,
      "hour_19": 12,
      "hour_20": 12,
      "hour_21": 18,
      "hour_22": 18,
      "hour_23": 18,
      "hour_24": 18
    },
    "ncm-daily-9345-Dwell_DomBed_Heat_Wknd": {
      "sched_type_limits_name": "TEMPERATURE",
      "hour_1": 18,
      "hour_2": 18,
      "hour_3": 18,
      "hour_4": 18,
      "hour_5": 18,
      "hour_6": 18,
      "hour_7": 18,
      "hour_8": 18,
      "hour_9": 18,
      "hour_10": 12,
      "hour_11": 12,
      "hour_12": 12,
      "hour_13": 12,
      "hour_14": 12,
      "hour_15": 12,
      "hour_16": 12,
      "hour_17": 12,
      "hour_18": 12,
      "hour_19": 12,
      "hour_20": 12,
      "hour_21": 18,
      "hour_22": 18,
      "hour_23": 18,
      "hour_24": 18
    },
    "ncm-daily-9346-Dwell_DomBed_Heat_Hol": {
      "sched_type_limits_name": "TEMPERATURE",
      "hour_1": 18,
      "hour_2": 18,
      "hour_3": 18,
      "hour_4": 18,
      "hour_5": 18,
      "hour_6": 18,
      "hour_7": 18,
      "hour_8": 18,
      "hour_9": 18,
      "hour_10": 12,
      "hour_11": 12,
      "hour_12": 12,
      "hour_13": 12,
      "hour_14": 12,
      "hour_15": 12,
      "hour_16": 12,
      "hour_17": 12,
      "hour_18": 12,
      "hour_19": 12,
      "hour_20": 12,
      "hour_21": 18,
      "hour_22": 18,
      "hour_23": 18,
      "hour_24": 18
    },
    "ncm-daily-9395-Dwell_DomLounge_Occ_Wkdy": {
      "sched_type_limits_name": "FRACTION",
      "hour_1": 0,
      "hour_2": 0,
      "hour_3": 0,
      "hour_4": 0,
      "hour_5": 0,
      "hour_6": 0,
      "hour_7": 0,
      "hour_8": 0,
      "hour_9": 0,
      "hour_10": 0,
      "hour_11": 0,
      "hour_12": 0,
      "hour_13": 0,
      "hour_14": 0,
      "hour_15": 0,
      "hour_16": 0,
      "hour_17": 0.5,
      "hour_18": 0.5,
      "hour_19": 1,
      "hour_20": 1,
      "hour_21": 1,
      "hour_22": 1,
      "hour_23": 0.666666667,
      "hour_24": 0
    },
    "ncm-daily-9396-Dwell_DomLounge_Occ_Wknd": {
      "sched_type_limits_name": "FRACTION",
      "hour_1": 0,
      "hour_2": 0,
      "hour_3": 0,
      "hour_4": 0,
      "hour_5": 0,
      "hour_6": 0,
      "hour_7": 0,
      "hour_8": 0,
      "hour_9": 0,
      "hour_10": 0,
      "hour_11": 0,
      "hour_12": 0,
      "hour_13": 0,
      "hour_14": 0,
      "hour_15": 0,
      "hour_16": 0,
      "hour_17": 0.5,
      "hour_18": 0.5,
      "hour_19": 1,
      "hour_20": 1,
      "hour_21": 1,
      "hour_22": 1,
      "hour_23": 0.666666667,
      "hour_24": 0
    },
    "ncm-daily-9397-Dwell_DomLounge_Occ_Hol": {
      "sched_type_limits_name": "FRACTION",
      "hour_1": 0,
      "hour_2": 0,
      "hour_3": 0,
      "hour_4": 0,
      "hour_5": 0,
      "hour_6": 0,
      "hour_7": 0,
      "hour_8": 0,
      "hour_9": 0,
      "hour_10": 0,
      "hour_11": 0,
      "hour_12": 0,
      "hour_13": 0,
      "hour_14": 0,
      "hour_15": 0,
      "hour_16": 0,
      "hour_17": 0.5,
      "hour_18": 0.5,
      "hour_19": 1,
      "hour_20": 1,
      "hour_21": 1,
      "hour_22": 1,
      "hour_23": 0.666666667,
      "hour_24": 0
    },
    "ncm-daily-9404-Dwell_DomLounge_Heat_Wkdy": {
      "sched_type_limits_name": "TEMPERATURE",
      "hour_1": 12,
      "hour_2": 12,
      "hour_3": 12,
      "hour_4": 12,
      "hour_5": 12,
      "hour_6": 12,
      "hour_7": 12,
      "hour_8": 12,
      "hour_9": 12,
      "hour_10": 12,
      "hour_11": 12,
      "hour_12": 12,
      "hour_13": 12,
      "hour_14": 12,
      "hour_15": 21,
      "hour_16": 21,
      "hour_17": 21,
      "hour_18": 21,
      "hour_19": 21,
      "hour_20": 21,
      "hour_21": 21,
      "hour_22": 21,
      "hour_23": 21,
      "hour_24": 12
    },
    "ncm-daily-9405-Dwell_DomLounge_Heat_Wknd": {
      "sched_type_limits_name": "TEMPERATURE",
      "hour_1": 12,
      "hour_2": 12,
      "hour_3": 12,
      "hour_4": 12,
      "hour_5": 12,
      "hour_6": 12,
      "hour_7": 12,
      "hour_8": 12,
      "hour_9": 12,
      "hour_10": 12,
      "hour_11": 12,
      "hour_12": 12,
      "hour_13": 12,
      "hour_14": 12,
      "hour_15": 21,
      "hour_16": 21,
      "hour_17": 21,
      "hour_18": 21,
      "hour_19": 21,
      "hour_20": 21,
      "hour_21": 21,
      "hour_22": 21,
      "hour_23": 21,
      "hour_24": 12
    },
    "ncm-daily-9406-Dwell_DomLounge_Heat_Hol": {
      "sched_type_limits_name": "TEMPERATURE",
      "hour_1": 12,
      "hour_2": 12,
      "hour_3": 12,
      "hour_4": 12,
      "hour_5": 12,
      "hour_6": 12,
      "hour_7": 12,
      "hour_8": 12,
      "hour_9": 12,
      "hour_10": 12,
      "hour_11": 12,
      "hour_12": 12,
      "hour_13": 12,
      "hour_14": 12,
      "hour_15": 21,
      "hour_16": 21,
      "hour_17": 21,
      "hour_18": 21,
      "hour_19": 21,
      "hour_20": 21,
      "hour_21": 21,
      "hour_22": 21,
      "hour_23": 21,
      "hour_24": 12
    },
    "ncm-daily-9335-Dwell_DomBed_Occ_Wkdy": {
      "sched_type_limits_name": "FRACTION",
      "hour_1": 1,
      "hour_2": 1,
      "hour_3": 1,
      "hour_4": 1,
      "hour_5": 1,
      "hour_6": 1,
      "hour_7": 1,
      "hour_8": 0.5,
      "hour_9": 0.25,
      "hour_10": 0,
      "hour_11": 0,
      "hour_12": 0,
      "hour_13": 0,
      "hour_14": 0,
      "hour_15": 0,
      "hour_16": 0,
      "hour_17": 0,
      "hour_18": 0,
      "hour_19": 0,
      "hour_20": 0,
      "hour_21": 0,
      "hour_22": 0,
      "hour_23": 0.25,
      "hour_24": 0.75
    },
    "ncm-daily-9336-Dwell_DomBed_Occ_Wknd": {
      "sched_type_limits_name": "FRACTION",
      "hour_1": 1,
      "hour_2": 1,
      "hour_3": 1,
      "hour_4": 1,
      "hour_5": 1,
      "hour_6": 1,
      "hour_7": 1,
      "hour_8": 0.5,
      "hour_9": 0.25,
      "hour_10": 0,
      "hour_11": 0,
      "hour_12": 0,
      "hour_13": 0,
      "hour_14": 0,
      "hour_15": 0,
      "hour_16": 0,
      "hour_17": 0,
      "hour_18": 0,
      "hour_19": 0,
      "hour_20": 0,
      "hour_21": 0,
      "hour_22": 0,
      "hour_23": 0.25,
      "hour_24": 0.75
    },
    "ncm-daily-9337-Dwell_DomBed_Occ_Hol": {
      "sched_type_limits_name": "FRACTION",
      "hour_1": 1,
      "hour_2": 1,
      "hour_3": 1,
      "hour_4": 1,
      "hour_5": 1,
      "hour_6": 1,
      "hour_7": 1,
      "hour_8": 0.5,
      "hour_9": 0.25,
      "hour_10": 0,
      "hour_11": 0,
      "hour_12": 0,
      "hour_13": 0,
      "hour_14": 0,
      "hour_15": 0,
      "hour_16": 0,
      "hour_17": 0,
      "hour_18": 0,
      "hour_19": 0,
      "hour_20": 0,
      "hour_21": 0,
      "hour_22": 0,
      "hour_23": 0.25,
      "hour_24": 0.75
    }
  },
  "Schedule:Week:Daily": {
    "ncm-weekly-3530-Dwell_DomBed_Heat_Wk1": {
      "monday_schedule_day_name": "ncm-daily-9344-Dwell_DomBed_Heat_Wkdy",
      "tuesday_schedule_day_name": "ncm-daily-9344-Dwell_DomBed_Heat_Wkdy",
      "wednesday_schedule_day_name": "ncm-daily-9344-Dwell_DomBed_Heat_Wkdy",
      "thursday_schedule_day_name": "ncm-daily-9344-Dwell_DomBed_Heat_Wkdy",
      "friday_schedule_day_name": "ncm-daily-9344-Dwell_DomBed_Heat_Wkdy",
      "saturday_schedule_day_name": "ncm-daily-9345-Dwell_DomBed_Heat_Wknd",
      "sunday_schedule_day_name": "ncm-daily-9345-Dwell_DomBed_Heat_Wknd",
      "holiday_schedule_day_name": "ncm-daily-9346-Dwell_DomBed_Heat_Hol",
      "summerdesignday_schedule_day_name": "ncm-daily-9346-Dwell_DomBed_Heat_Hol",
      "winterdesignday_schedule_day_name": "ncm-daily-9346-Dwell_DomBed_Heat_Hol",
      "customday1_schedule_day_name": "ncm-daily-9346-Dwell_DomBed_Heat_Hol",
      "customday2_schedule_day_name": "ncm-daily-9346-Dwell_DomBed_Heat_Hol"
    },
    "ncm-weekly-3557-Dwell_DomLounge_Occ_Wk1": {
      "monday_schedule_day_name": "ncm-daily-9395-Dwell_DomLounge_Occ_Wkdy",
      "tuesday_schedule_day_name": "ncm-daily-9395-Dwell_DomLounge_Occ_Wkdy",
      "wednesday_schedule_day_name": "ncm-daily-9395-Dwell_DomLounge_Occ_Wkdy",
      "thursday_schedule_day_name": "ncm-daily-9395-Dwell_DomLounge_Occ_Wkdy",
      "friday_schedule_day_name": "ncm-daily-9395-Dwell_DomLounge_Occ_Wkdy",
      "saturday_schedule_day_name": "ncm-daily-9396-Dwell_DomLounge_Occ_Wknd",
      "sunday_schedule_day_name": "ncm-daily-9396-Dwell_DomLounge_Occ_Wknd",
      "holiday_schedule_day_name": "ncm-daily-9397-Dwell_DomLounge_Occ_Hol",
      "summerdesignday_schedule_day_name": "ncm-daily-9397-Dwell_DomLounge_Occ_Hol",
      "winterdesignday_schedule_day_name": "ncm-daily-9397-Dwell_DomLounge_Occ_Hol",
      "customday1_schedule_day_name": "ncm-daily-9397-Dwell_DomLounge_Occ_Hol",
      "customday2_schedule_day_name": "ncm-daily-9397-Dwell_DomLounge_Occ_Hol"
    },
    "ncm-weekly-3555-Dwell_DomLounge_Heat_Wk1": {
      "monday_schedule_day_name": "ncm-daily-9404-Dwell_DomLounge_Heat_Wkdy",
      "tuesday_schedule_day_name": "ncm-daily-9404-Dwell_DomLounge_Heat_Wkdy",
      "wednesday_schedule_day_name": "ncm-daily-9404-Dwell_DomLounge_Heat_Wkdy",
      "thursday_schedule_day_name": "ncm-daily-9404-Dwell_DomLounge_Heat_Wkdy",
      "friday_schedule_day_name": "ncm-daily-9404-Dwell_DomLounge_Heat_Wkdy",
      "saturday_schedule_day_name": "ncm-daily-9405-Dwell_DomLounge_Heat_Wknd",
      "sunday_schedule_day_name": "ncm-daily-9405-Dwell_DomLounge_Heat_Wknd",
      "holiday_schedule_day_name": "ncm-daily-9406-Dwell_DomLounge_Heat_Hol",
      "summerdesignday_schedule_day_name": "ncm-daily-9406-Dwell_DomLounge_Heat_Hol",
      "winterdesignday_schedule_day_name": "ncm-daily-9406-Dwell_DomLounge_Heat_Hol",
      "customday1_schedule_day_name": "ncm-daily-9406-Dwell_DomLounge_Heat_Hol",
      "customday2_schedule_day_name": "ncm-daily-9406-Dwell_DomLounge_Heat_Hol"
    },
    "ncm-weekly-3532-Dwell_DomBed_Occ_Wk1": {
      "monday_schedule_day_name": "ncm-daily-9335-Dwell_DomBed_Occ_Wkdy",
      "tuesday_schedule_day_name": "ncm-daily-9335-Dwell_DomBed_Occ_Wkdy",
      "wednesday_schedule_day_name": "ncm-daily-9335-Dwell_DomBed_Occ_Wkdy",
      "thursday_schedule_day_name": "ncm-daily-9335-Dwell_DomBed_Occ_Wkdy",
      "friday_schedule_day_name": "ncm-daily-9335-Dwell_DomBed_Occ_Wkdy",
      "saturday_schedule_day_name": "ncm-daily-9336-Dwell_DomBed_Occ_Wknd",
      "sunday_schedule_day_name": "ncm-daily-9336-Dwell_DomBed_Occ_Wknd",
      "holiday_schedule_day_name": "ncm-daily-9337-Dwell_DomBed_Occ_Hol",
      "summerdesignday_schedule_day_name": "ncm-daily-9337-Dwell_DomBed_Occ_Hol",
      "winterdesignday_schedule_day_name": "ncm-daily-9337-Dwell_DomBed_Occ_Hol",
      "customday1_schedule_day_name": "ncm-daily-9337-Dwell_DomBed_Occ_Hol",
      "customday2_schedule_day_name": "ncm-daily-9337-Dwell_DomBed_Occ_Hol"
    }
  },
  "Schedule:Year": {
    "ncm-annual-3232-Dwell_DomBed_Heat": {
      "schedule_type_limits_name": "TEMPERATURE",
      "schedule_weeks": [
        {
          "schedule_week_name": "ncm-weekly-3530-Dwell_DomBed_Heat_Wk1",
          "start_month": 1,
          "start_day": 1,
          "end_month": 12,
          "end_day": 31
        }
      ]
    },
    "ncm-annual-3249-Dwell_DomLounge_Occ": {
      "schedule_type_limits_name": "FRACTION",
      "schedule_weeks": [
        {
          "schedule_week_name": "ncm-weekly-3557-Dwell_DomLounge_Occ_Wk1",
          "start_month": 1,
          "start_day": 1,
          "end_month": 12,
          "end_day": 31
        }
      ]
    },
    "ncm-annual-3252-Dwell_DomLounge_Heat": {
      "schedule_type_limits_name": "TEMPERATURE",
      "schedule_weeks": [
        {
          "schedule_week_name": "ncm-weekly-3555-Dwell_DomLounge_Heat_Wk1",
          "start_month": 1,
          "start_day": 1,
          "end_month": 12,
          "end_day": 31
        }
      ]
    },
    "ncm-annual-3229-Dwell_DomBed_Occ": {
      "schedule_type_limits_name": "FRACTION",
      "schedule_weeks": [
        {
          "schedule_week_name": "ncm-weekly-3532-Dwell_DomBed_Occ_Wk1",
          "start_month": 1,
          "start_day": 1,
          "end_month": 12,
          "end_day": 31
        }
      ]
    }
  }
}
```

</details>
