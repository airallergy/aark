"""CIBSE TM52:2013 adaptive overheating criteria."""
# ruff: noqa: N802,N803,N806

from typing import TYPE_CHECKING

import numpy as np

import aark
import aark.arr

if TYPE_CHECKING:
    from collections.abc import Iterable

    from aark import MonthDay
    from aark.arr import BoolArr2D, FloatArr1D, FloatArr2D


SUMMER_START_MONTH_DAY = (5, 1)
SUMMER_END_MONTH_DAY = (9, 30)
CRITERION_1_THRESHOLD = 3  # %
CRITERION_2_THRESHOLD = 6  # K h
CRITERION_3_THRESHOLD = 4  # K


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
    aark.validate_positive_n_timesteps(n_hourly_timesteps)
    aark.arr.validate_full_days(Top_1d, n_hourly_timesteps)
    validate_assessment_period(
        start_month_day, end_month_day, SUMMER_START_MONTH_DAY, SUMMER_END_MONTH_DAY
    )
    validate_category(category)

    # convert
    n_daily_timesteps = 24 * n_hourly_timesteps

    # normalise more
    Top = Top_1d.reshape((-1, n_daily_timesteps))
    occupancy = occupancy_1d.reshape((-1, n_daily_timesteps))

    # convert more
    Tmax = _calc_Tmax(Trm, category)
    occupied = occupancy > 0

    # validate more
    if not occupied.any():
        raise ValueError(f"Zero occupancy: {occupancy}.")

    start_date = aark.as_date(start_month_day)
    end_date = aark.as_date(end_month_day)
    datetimes = aark.arr.date_linspace(start_date, end_date, n_daily_timesteps)
    datetimes_2d = datetimes.reshape(-1, n_daily_timesteps)

    Tmax_2d = np.broadcast_to(Tmax[:, None], (Tmax.size, n_daily_timesteps))
    aark.arr.validate_equal_shape(Top, occupancy, datetimes_2d, Tmax_2d)

    return _calc_deltaT(Top, Tmax), occupied, n_hourly_timesteps


# -----------------------------------------------------------------------------
# BS EN 15251:2007
# -----------------------------------------------------------------------------


def calc_Trm(Tod_1d: Iterable[float]) -> FloatArr1D:
    """Calculate daily exponentially weighted running mean temperature.

    Notes
    -----
    The final seven days of the provided one-year daily mean outdoor air
    temperature data are used to initialise `Trm`.

    The recurrence is vectorised. For example, with `alpha = 0.8`:

    ```python
    Trm[i + 1] = 0.8 * Trm[i] + 0.2 * Tod[i]
    ```

    Let `k[i] = 0.2 * Tod[i]`. Expanding the recurrence gives:

    ```python
    Trm[1] = 0.8 * Trm[0] + 0.8 ** 0 * k[0]
    Trm[2] = 0.8 ** 2 * Trm[0] + 0.8 ** 1 * k[0] + 0.8 ** 0 * k[1]
    ```

    Therefore:

    ```python
    Trm[i + 1] = np.dot(
        [0.8 ** (i + 1), 0.8 ** i, ..., 0.8 ** 0],
        [Trm[0], k[0], k[1], ..., k[i]],
    )
    ```
    """
    alpha = 0.8

    # normalise
    Tod = aark.arr.as_1d(Tod_1d)

    # validate
    aark.arr.validate_finite(Tod)

    if Tod.size not in (365, 366):
        raise ValueError(
            f"Tod must contain a complete year of 365 or 366 days: {Tod.size}."
        )

    # TM52 equation 2.3 is a fixed seven-day approximation for alpha = 0.8.
    init_weights = np.array((1.0, 0.8, 0.6, 0.5, 0.4, 0.3, 0.2))
    init_Trm = np.dot(init_weights, Tod[-1:-8:-1]) / 3.8

    weights = np.power(alpha, range(Tod.size, 0, -1))
    k = (1 - alpha) * Tod[:-1]
    terms = np.append(init_Trm, k)

    return np.add.accumulate(weights * terms) / weights


def _calc_Tmax(Trm: FloatArr1D, category: int) -> FloatArr1D:
    """Calculate the maximum acceptable operative temperature."""
    return 0.33 * Trm + 21.8 + (category - 2)


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
# Validation
# -----------------------------------------------------------------------------


def validate_category(category: int) -> None:
    """Validate an adaptive comfort category."""
    if category not in (1, 2, 3):
        raise ValueError(f"Invalid adaptive category: {category}.")


def validate_assessment_period(
    start_month_day: MonthDay,
    end_month_day: MonthDay,
    min_start_month_day: MonthDay = (1, 1),
    max_end_month_day: MonthDay = (12, 31),
) -> None:
    """Validate that an assessment period lies within a permitted period."""
    if not (
        aark.as_date(min_start_month_day)
        <= aark.as_date(start_month_day)
        <= aark.as_date(end_month_day)
        <= aark.as_date(max_end_month_day)
    ):
        raise ValueError(
            f"Invalid assessment period: {start_month_day}, {end_month_day}."
        )
