"""TM52:2013 EnergyPlus outputs."""

from typing import TYPE_CHECKING

import aark.ep.generic

if TYPE_CHECKING:
    from eppy.modeleditor import IDF

VAR_NAMES = ("Zone Operative Temperature", "Zone People Occupant Count")


def apply(idf: IDF) -> None:
    """Add the EnergyPlus outputs required to assess the TM52 criteria."""
    for var_name in VAR_NAMES:
        aark.ep.generic.add_obj(
            idf,
            "Output:Variable",
            Key_Value="*",
            Variable_Name=var_name,
            Reporting_Frequency="Hourly",
        )
