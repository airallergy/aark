"""Create hybrid EnergyPlus weather: https://doi.org/10.26868/25222708.2023.1475."""

from typing import TYPE_CHECKING

import aark._utils
import aark.epw._pact
import aark.epw._utils
from aark._utils import LEAP_REF_YEAR, NON_LEAP_REF_YEAR, YEAR_START_MONTH_DAY

if TYPE_CHECKING:
    from typing import TextIO

    from aark._utils import Endpoint


def splice(*endpoints: Endpoint[TextIO]) -> list[str]:
    """Return hybrid weather lines spliced from annual weather intervals.

    Parameters
    ----------
    endpoints
        `(end_month_day, f)` pairs with inclusive `(month, day)` endpoints and
        seekable text handles. Endpoints must be unique
        and include 31 December.

    Returns
    -------
    list[str]
        The first supplied file's header with updated comments, followed by
        unchanged selected records in calendar order, including line endings.
    """
    # validate aark requirements
    for _, f in endpoints:
        aark.epw._pact.validate_full_year_hourly(f)

    # validate user inputs
    _validate_endpoints(*endpoints)

    # initiate with the first file handle
    (_, f), *_ = endpoints
    lines = aark.epw._utils.read_lines(f)

    n_lines = len(lines)
    hybrid_lines = lines[:8]
    hybrid_lines[5] = f"COMMENTS 1,{aark.epw._utils.prefix('hybrid')}\n"
    hybrid_lines[6] = "COMMENTS 2,https://doi.org/10.26868/25222708.2023.1475\n"

    ref_year = {8768: NON_LEAP_REF_YEAR, 8792: LEAP_REF_YEAR}[n_lines]
    year_start = aark._utils.as_date(YEAR_START_MONTH_DAY, ref_year)

    # splice
    for start_month_day, end_month_day, f in aark._utils.expand_endpoints(
        endpoints, year=ref_year
    ):
        lines = aark.epw._utils.read_lines(f)
        start_date = aark._utils.as_date(start_month_day, ref_year)
        end_date = aark._utils.as_date(end_month_day, ref_year)

        start_idx = 8 + (start_date - year_start).days * 24
        end_idx = 8 + ((end_date - year_start).days + 1) * 24

        hybrid_lines.extend(lines[start_idx:end_idx])

    return hybrid_lines


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------


def _validate_endpoints(*endpoints: Endpoint[TextIO]) -> None:
    """Validate matching line counts and leap-day compatibility."""
    # input files must share one line count
    line_counts = {len(aark.epw._utils.read_lines(f)) for _, f in endpoints}

    if len(line_counts) != 1:
        raise ValueError(f"Different line counts in weather files: {line_counts}.")

    # non-leap inputs must not have a 29 february endpoint
    (n_lines,) = line_counts

    if (n_lines == 8768) and ((2, 29) in {month_day for month_day, _ in endpoints}):
        raise ValueError(f"Invalid endpoints for non-leap weather files: {endpoints}.")
