"""Array utilities."""

import datetime as dt
from typing import TYPE_CHECKING

import numpy as np

import aark._utils

if TYPE_CHECKING:
    from collections.abc import Iterable

    type Arr[
        ShapeT: tuple[int, *tuple[int, ...]] = tuple[int, *tuple[int, ...]],
        DTypeT: np.dtype = np.dtype[np.generic],
    ] = np.ndarray[ShapeT, DTypeT]
    type Arr1D[T: np.generic = np.generic] = Arr[tuple[int], np.dtype[T]]
    type Arr2D[T: np.generic = np.generic] = Arr[tuple[int, int], np.dtype[T]]
    type BoolArr1D = Arr1D[np.bool_]
    type BoolArr2D = Arr2D[np.bool_]
    type FloatArr1D = Arr1D[np.floating]
    type FloatArr2D = Arr2D[np.floating]


def as_1d(iterable: Iterable[float]) -> FloatArr1D:
    """Convert an iterable of floats to a 1D float array."""
    return np.fromiter(iterable, dtype=float)


def round[ShapeT: tuple[int, *tuple[int, ...]], ScalarT: np.floating](
    arr: Arr[ShapeT, np.dtype[ScalarT]],
) -> Arr[ShapeT, np.dtype[ScalarT]]:
    """Round values to whole numbers, with half values rounded away from zero."""
    return np.asarray(np.trunc(arr + np.copysign(0.5, arr)), dtype=arr.dtype)


def date_linspace(
    start_date: dt.date, end_date: dt.date, n_daily_timesteps: int
) -> Arr1D[np.datetime64]:
    """Return a full-day datetime array over the interval [start_date, end_date].

    Timesteps are assumed to be a whole number of minutes.
    """
    # normalise
    start_date = dt.date(start_date.year, start_date.month, start_date.day)
    end_date = dt.date(end_date.year, end_date.month, end_date.day)

    # validate
    aark._utils.validate_n_timesteps(n_daily_timesteps)

    minute_step, remainder = divmod(24 * 60, n_daily_timesteps)
    if remainder:
        raise ValueError(
            f"Daily timestep count cannot be converted to a whole-minute timestep: {n_daily_timesteps}."
        )

    return np.arange(
        np.datetime64(start_date, "m"),
        np.datetime64(end_date + dt.timedelta(days=1), "m"),
        np.timedelta64(minute_step, "m"),
    )


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------


def validate_finite(*arrs: Arr1D) -> None:
    """Validate that 1D arrays are non-empty and finite."""
    for arr in arrs:
        if arr.size == 0:
            raise ValueError(f"Empty array: {arr}.")

        if not np.all(np.isfinite(arr)):
            raise ValueError(f"Non-finite array: {arr}.")


def validate_equal_shape(arr: Arr, *arrs: Arr) -> None:
    """Validate that arrays have the same shape."""
    arr_shapes = {item.shape for item in (arr, *arrs)}
    if len(arr_shapes) > 1:
        raise ValueError(f"Array shapes differ: {arr_shapes}.")


def validate_full_days(arr: Arr1D, n_hourly_timesteps: int) -> None:
    """Validate that a time series contains full days of values."""
    n_daily_timesteps = 24 * n_hourly_timesteps

    if arr.size % n_daily_timesteps != 0:
        raise ValueError(
            f"Time series does not contain full days: {arr.size} values at {n_hourly_timesteps} hourly timesteps."
        )
