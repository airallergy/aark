"""TM59:2017 EnergyPlus outputs."""

from typing import TYPE_CHECKING

import aark.tm52.outputs

if TYPE_CHECKING:
    from eppy.modeleditor import IDF


def apply(idf: IDF) -> None:
    """Add the EnergyPlus outputs required to assess the TM59 criteria."""
    aark.tm52.outputs.apply(idf)
