"""TM59:2017 overheating assessment criteria."""
# ruff: noqa: N803,N806

from typing import TYPE_CHECKING

import numpy as np

import aark
import aark.arr
import aark.tm52.criteria
from aark import LEAP_REF_YEAR, NON_LEAP_REF_YEAR
from aark.tm59.data import AWAKE_END_HOUR, AWAKE_START_HOUR

if TYPE_CHECKING:
    from collections.abc import Iterable

    from eppy.modeleditor import IDF

    from aark import MonthDay
    from aark.arr import BoolArr1D, FloatArr1D, FloatArr2D


GUIDE_A_TEMPERATURE_THRESHOLD = 26  # °C
COMMUNAL_CORRIDOR_TEMPERATURE_THRESHOLD = 28  # °C
CRITERION_B_THRESHOLD = 1  # %
MECHANICAL_VENT_THRESHOLD = 3  # %
COMMUNAL_CORRIDOR_THRESHOLD = 3  # %


def _parsed_non_adaptive_criterion_args(
    Top_1d: Iterable[float],
    start_month_day: MonthDay,
    end_month_day: MonthDay,
    n_hourly_timesteps: int,
    is_leap: bool = False,
) -> FloatArr2D:
    """Convert and validate inputs shared by the three non-adaptive criteria."""
    # normalise
    Top_1d = aark.arr.as_1d(Top_1d)

    # validate
    aark.arr.validate_finite(Top_1d)
    aark.validate_positive_n_timesteps(n_hourly_timesteps)
    aark.arr.validate_full_days(Top_1d, n_hourly_timesteps)
    aark.tm52.criteria.validate_assessment_period(start_month_day, end_month_day)

    # convert
    n_daily_timesteps = 24 * n_hourly_timesteps

    # normalise more
    Top = Top_1d.reshape((-1, n_daily_timesteps))

    # validate more
    ref_year = LEAP_REF_YEAR if is_leap else NON_LEAP_REF_YEAR
    start_date = aark.as_date(start_month_day, ref_year)
    end_date = aark.as_date(end_month_day, ref_year)

    datetimes = aark.arr.date_linspace(start_date, end_date, n_daily_timesteps)
    datetimes_2d = datetimes.reshape(-1, n_daily_timesteps)
    aark.arr.validate_equal_shape(Top, datetimes_2d)

    return Top


def get_daily_awake_mask(n_hourly_timesteps: int) -> BoolArr1D:
    """Return the daily awake mask."""
    aark.validate_positive_n_timesteps(n_hourly_timesteps)

    hour_idxs = np.arange(24, dtype=int)
    hourly_mask = (hour_idxs >= AWAKE_START_HOUR) & (hour_idxs < AWAKE_END_HOUR)
    timestep_mask = np.repeat(hourly_mask[:, None], n_hourly_timesteps, axis=1)
    return timestep_mask.ravel()


def calc_fixed_temperature_exceedance(
    assessed_temperatures: FloatArr1D,
    temperature_threshold: float,
    criterion_threshold: float,
    n_hourly_timesteps: int,
) -> dict[str, object]:
    """Calculate temperature exceedance with a fixed temperature threshold."""
    exceeded = assessed_temperatures > temperature_threshold
    n_exceeded_timesteps = int(exceeded.sum())
    n_exceeded_hours = n_exceeded_timesteps / n_hourly_timesteps

    n_assessed_timesteps = assessed_temperatures.size
    n_assessed_hours = n_assessed_timesteps / n_hourly_timesteps

    passed = n_exceeded_timesteps * 100 <= criterion_threshold * n_assessed_timesteps

    return {
        "n_exceeded_hours": n_exceeded_hours,
        "n_assessed_hours": n_assessed_hours,
        "threshold": criterion_threshold,
        "passed": passed,
    }


# -----------------------------------------------------------------------------
# Criteria
# -----------------------------------------------------------------------------


def assess_criterion_a(
    Top_1d: Iterable[float],
    Trm_1d: Iterable[float],
    occupancy_1d: Iterable[float],
    start_month_day: MonthDay,
    end_month_day: MonthDay,
    n_hourly_timesteps: int = 1,
    category: int = 2,
    awake_only: bool = False,
) -> dict[str, object]:
    """Assess TM59 criterion a.

    Occupied hours exceeding the adaptive limit, from TM52 criterion 1.
    """
    validate_category_not_3(category)

    if awake_only:
        daily_awake = get_daily_awake_mask(n_hourly_timesteps)

        occupancy_1d = aark.arr.as_1d(occupancy_1d)
        aark.arr.validate_full_days(occupancy_1d, n_hourly_timesteps)
        occupancy = occupancy_1d.reshape((-1, 24 * n_hourly_timesteps))

        occupancy *= daily_awake
        occupancy_1d = occupancy.ravel()

    return aark.tm52.criteria.assess_criterion_1(
        Top_1d,
        Trm_1d,
        occupancy_1d,
        start_month_day,
        end_month_day,
        n_hourly_timesteps,
        category,
    )


def assess_criterion_b(
    Top_1d: Iterable[float],
    start_month_day: MonthDay,
    end_month_day: MonthDay,
    n_hourly_timesteps: int = 1,
    is_leap: bool = False,
) -> dict[str, object]:
    """Assess TM59 criterion b.

    Sleeping hours exceeding 26 °C, from Guide A.
    """
    Top = _parsed_non_adaptive_criterion_args(
        Top_1d, start_month_day, end_month_day, n_hourly_timesteps, is_leap
    )

    daily_asleep = ~get_daily_awake_mask(n_hourly_timesteps)
    result = calc_fixed_temperature_exceedance(
        Top[:, daily_asleep].ravel(),
        GUIDE_A_TEMPERATURE_THRESHOLD,
        CRITERION_B_THRESHOLD,
        n_hourly_timesteps,
    )

    return {
        "n_exceeded_hours": result["n_exceeded_hours"],
        "n_sleeping_hours": result["n_assessed_hours"],
        "threshold": result["threshold"],
        "passed": result["passed"],
    }


def assess_mechanical_vent(
    Top_1d: Iterable[float],
    occupancy_1d: Iterable[float],
    start_month_day: MonthDay,
    end_month_day: MonthDay,
    n_hourly_timesteps: int = 1,
    is_leap: bool = False,
) -> dict[str, object]:
    """Assess TM59 criterion for mechanically ventilated homes.

    Occupied hours exceeding 26 °C, from Guide A.
    """
    Top = _parsed_non_adaptive_criterion_args(
        Top_1d, start_month_day, end_month_day, n_hourly_timesteps, is_leap
    )

    # parse occupancy
    occupancy_1d = aark.arr.as_1d(occupancy_1d)
    aark.arr.validate_finite(occupancy_1d)
    occupancy = occupancy_1d.reshape(Top.shape)
    occupied = occupancy > 0

    if not occupied.any():
        raise ValueError(f"Zero occupancy: {occupancy}.")

    result = calc_fixed_temperature_exceedance(
        Top[occupied],
        GUIDE_A_TEMPERATURE_THRESHOLD,
        MECHANICAL_VENT_THRESHOLD,
        n_hourly_timesteps,
    )

    return {
        "n_exceeded_hours": result["n_exceeded_hours"],
        "n_occupied_hours": result["n_assessed_hours"],
        "threshold": result["threshold"],
        "passed": result["passed"],
    }


def assess_communal_corridor(
    Top_1d: Iterable[float],
    start_month_day: MonthDay,
    end_month_day: MonthDay,
    n_hourly_timesteps: int = 1,
    is_leap: bool = False,
) -> dict[str, object]:
    """Assess TM59 criterion for communal corridors.

    Hours exceeding 28 °C.
    """
    Top = _parsed_non_adaptive_criterion_args(
        Top_1d, start_month_day, end_month_day, n_hourly_timesteps, is_leap
    )

    return calc_fixed_temperature_exceedance(
        Top.ravel(),
        COMMUNAL_CORRIDOR_TEMPERATURE_THRESHOLD,
        COMMUNAL_CORRIDOR_THRESHOLD,
        n_hourly_timesteps,
    )


# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------


def apply_outputs(idf: IDF) -> None:
    """Add the EnergyPlus outputs required to assess the TM59 criteria."""
    aark.tm52.criteria.apply_outputs(idf)


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------


def validate_category_not_3(category: int) -> None:
    """Validate that an adaptive comfort category is not 3."""
    if category == 3:
        raise ValueError(f"Invalid adaptive category: {category}.")
