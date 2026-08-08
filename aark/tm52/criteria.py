"""TM52:2013 assessment criteria."""

from typing import TYPE_CHECKING

import numpy as np

import aark._utils
import aark.arr
import aark.ep.obj
import aark.tm52.adaptive

if TYPE_CHECKING:
    from collections.abc import Iterable

    from eppy.modeleditor import IDF

    from aark._utils import MonthDay
    from aark.arr import BoolArr2D, FloatArr1D, FloatArr2D


SUMMER_START_MONTH_DAY = (5, 1)
SUMMER_END_MONTH_DAY = (9, 30)
CRITERION_1_THRESHOLD = 3  # %
CRITERION_2_THRESHOLD = 6  # K h
CRITERION_3_THRESHOLD = 4  # K
OUTPUT_VAR_NAMES = ("Zone Operative Temperature", "Zone People Occupant Count")


def _parsed_criterion_args(
    Top_1d: Iterable[float],
    Trm_1d: Iterable[float],
    occupancy_1d: Iterable[float],
    start_month_day: MonthDay,
    end_month_day: MonthDay,
    n_hourly_timesteps: int,
    category: int,
) -> tuple[FloatArr2D, BoolArr2D, int]:
    """Convert and validate inputs shared by the three criteria."""
    # normalise
    Top_1d = aark.arr.as_1d(Top_1d)
    Trm = aark.arr.as_1d(Trm_1d)
    occupancy_1d = aark.arr.as_1d(occupancy_1d)

    # validate
    aark.arr.validate_finite(Top_1d, Trm, occupancy_1d)
    aark._utils.validate_n_timesteps(n_hourly_timesteps)
    aark.arr.validate_full_days(Top_1d, n_hourly_timesteps)
    aark._utils.validate_subperiod(
        start_month_day, end_month_day, SUMMER_START_MONTH_DAY, SUMMER_END_MONTH_DAY
    )
    aark.tm52.adaptive.validate_category(category)

    # convert
    n_daily_timesteps = 24 * n_hourly_timesteps

    # normalise more
    Top = Top_1d.reshape((-1, n_daily_timesteps))
    occupancy = occupancy_1d.reshape((-1, n_daily_timesteps))

    # convert more
    Tmax = aark.tm52.adaptive.calc_Tmax(Trm, category)
    occupied = occupancy > 0

    # validate more
    if not occupied.any():
        raise ValueError(f"Zero occupancy: {occupancy}.")

    start_date = aark._utils.as_date(start_month_day)
    end_date = aark._utils.as_date(end_month_day)
    datetimes = aark.arr.date_linspace(start_date, end_date, n_daily_timesteps)
    datetimes_2d = datetimes.reshape(-1, n_daily_timesteps)

    Tmax_2d = np.broadcast_to(Tmax[:, None], (Tmax.size, n_daily_timesteps))
    aark.arr.validate_equal_shape(Top, occupancy, datetimes_2d, Tmax_2d)

    return _calc_deltaT(Top, Tmax), occupied, n_hourly_timesteps


def _calc_deltaT(Top: FloatArr2D, Tmax: FloatArr1D) -> FloatArr2D:
    """Calculate the operative temperature exceedance."""
    return aark.arr.round(Top - Tmax[:, None])


# -----------------------------------------------------------------------------
# Criteria
# -----------------------------------------------------------------------------


def assess_criterion_1(
    Top_1d: Iterable[float],
    Trm_1d: Iterable[float],
    occupancy_1d: Iterable[float],
    start_month_day: MonthDay,
    end_month_day: MonthDay,
    n_hourly_timesteps: int = 1,
    category: int = 2,
) -> dict[str, object]:
    """Assess TM52 criterion 1.

    Hours of exceedance.
    """
    deltaT, occupied, n_hourly_timesteps = _parsed_criterion_args(
        Top_1d,
        Trm_1d,
        occupancy_1d,
        start_month_day,
        end_month_day,
        n_hourly_timesteps,
        category,
    )

    # calculate criterion metric
    exceeded = occupied & (deltaT >= 1)
    n_exceeded_timesteps = int(exceeded.sum())
    n_exceeded_hours = n_exceeded_timesteps / n_hourly_timesteps

    # calculate other return values
    n_occupied_timesteps = int(occupied.sum())
    n_occupied_hours = n_occupied_timesteps / n_hourly_timesteps

    passed = bool(
        n_exceeded_timesteps * 100 <= CRITERION_1_THRESHOLD * n_occupied_timesteps
    )

    return {
        "n_exceeded_hours": n_exceeded_hours,
        "n_occupied_hours": n_occupied_hours,
        "threshold": CRITERION_1_THRESHOLD,
        "passed": passed,
    }


def assess_criterion_2(
    Top_1d: Iterable[float],
    Trm_1d: Iterable[float],
    occupancy_1d: Iterable[float],
    start_month_day: MonthDay,
    end_month_day: MonthDay,
    n_hourly_timesteps: int = 1,
    category: int = 2,
) -> dict[str, object]:
    """Assess TM52 criterion 2.

    Daily weighted exceedance.
    """
    deltaT, occupied, n_hourly_timesteps = _parsed_criterion_args(
        Top_1d,
        Trm_1d,
        occupancy_1d,
        start_month_day,
        end_month_day,
        n_hourly_timesteps,
        category,
    )

    # calculate criterion metric
    exceedance = np.maximum(deltaT, 0)
    max_daily_degree_hours = (
        int((exceedance * occupied).sum(axis=1).max()) / n_hourly_timesteps
    )

    # calculate other return values
    passed = bool(max_daily_degree_hours <= CRITERION_2_THRESHOLD)

    return {
        "max_daily_degree_hours": max_daily_degree_hours,
        "threshold": CRITERION_2_THRESHOLD,
        "passed": passed,
    }


def assess_criterion_3(
    Top_1d: Iterable[float],
    Trm_1d: Iterable[float],
    occupancy_1d: Iterable[float],
    start_month_day: MonthDay,
    end_month_day: MonthDay,
    n_hourly_timesteps: int = 1,
    category: int = 2,
) -> dict[str, object]:
    """Assess TM52 criterion 3.

    Upper limit temperature.
    """
    deltaT, occupied, _ = _parsed_criterion_args(
        Top_1d,
        Trm_1d,
        occupancy_1d,
        start_month_day,
        end_month_day,
        n_hourly_timesteps,
        category,
    )

    # calculate criterion metric
    max_exceedance = int(deltaT[occupied].max())

    # calculate other return values
    passed = bool(max_exceedance <= CRITERION_3_THRESHOLD)

    return {
        "max_exceedance": max_exceedance,
        "threshold": CRITERION_3_THRESHOLD,
        "passed": passed,
    }


# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------


def apply_outputs(idf: IDF) -> None:
    """Add the EnergyPlus outputs required to assess the TM52 criteria."""
    for var_name in OUTPUT_VAR_NAMES:
        aark.ep.obj.add(
            idf,
            "Output:Variable",
            Key_Value="*",
            Variable_Name=var_name,
            Reporting_Frequency="Hourly",
        )
