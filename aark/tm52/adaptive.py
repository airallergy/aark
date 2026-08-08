"""BS EN 15251:2007 adaptive comfort calculations."""

from typing import TYPE_CHECKING

import numpy as np

import aark.arr

if TYPE_CHECKING:
    from collections.abc import Iterable

    from aark.arr import FloatArr1D


def calc_Trm(Tod_1d: Iterable[float]) -> FloatArr1D:
    """Calculate daily exponentially weighted running mean temperature.

    `Tod_1d` must contain a complete year of daily mean outdoor air temperatures. The
    final seven days are treated as the days preceding 1 January when initialising
    `Trm`.

    Notes
    -----
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

    # equation 2.3 is a fixed seven-day approximation for alpha = 0.8.
    init_weights = np.array((1.0, 0.8, 0.6, 0.5, 0.4, 0.3, 0.2))
    init_Trm = np.dot(init_weights, Tod[-1:-8:-1]) / 3.8

    weights = np.power(alpha, range(Tod.size, 0, -1))
    k = (1 - alpha) * Tod[:-1]
    terms = np.append(init_Trm, k)

    return np.add.accumulate(weights * terms) / weights


def calc_Tmax(Trm: FloatArr1D, category: int) -> FloatArr1D:
    """Calculate the maximum acceptable operative temperature."""
    return 0.33 * Trm + 21.8 + (category - 2)


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------


def validate_category(category: int) -> None:
    """Validate an adaptive comfort category."""
    if category not in (1, 2, 3):
        raise ValueError(f"Invalid adaptive category: {category}.")
