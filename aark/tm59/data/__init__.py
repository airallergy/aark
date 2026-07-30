"""CIBSE TM59:2017 source data."""

import csv
import importlib.resources
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


# unit / room types
COMMUNAL_CORRIDOR_TYPE = "communal_corridor"
STUDIO_TYPE = "studio"
BEDROOM_TYPES = frozenset({"single_bedroom", "double_bedroom"})
N_BEDROOMS_DEPENDENT_ROOM_TYPES = frozenset({"living_kitchen", "living", "kitchen"})
HABITABLE_ROOM_TYPES = (
    BEDROOM_TYPES | N_BEDROOMS_DEPENDENT_ROOM_TYPES | frozenset({STUDIO_TYPE})
)
ANCILLARY_ROOM_TYPES = frozenset({"bathroom", "hall"})
DWELLING_ROOM_TYPES = HABITABLE_ROOM_TYPES | ANCILLARY_ROOM_TYPES
ALL_ROOM_TYPES = DWELLING_ROOM_TYPES | frozenset({COMMUNAL_CORRIDOR_TYPE})


# -----------------------------------------------------------------------------
# Internal gain profiles
# -----------------------------------------------------------------------------


class InternalGainProfiles:
    """Provide TM59 internal gain profiles."""

    __slots__ = ("rows",)

    rows: tuple[MappingProxyType[str, str], ...]

    def __init__(self) -> None:
        """Read the internal gain profiles."""
        resource = importlib.resources.files(__package__).joinpath(
            "internal_gain_profiles.csv"
        )

        with resource.open() as f:
            reader = csv.DictReader(f)
            self.rows = tuple(map(MappingProxyType, reader))

    def get_row(self, gain_type: str, room_type: str = "") -> Mapping[str, str]:
        """Get the row for the given gain type and room type."""
        (row,) = (
            row
            for row in self.rows
            if (row["gain_type"] == gain_type) and (row["room_type"] == room_type)
        )
        return row

    def get_peak_load(self, gain_type: str, room_type: str = "") -> str:
        """Get the peak load, including latent load per person for occupancy."""
        row = self.get_row(gain_type, room_type)

        peak_load = int(row["peak_sensible"])

        if gain_type == "occupancy":
            # this is definitely an integer, `//` is used for typing purposes
            peak_load = (peak_load + int(row["peak_latent"])) // int(row["n_people"])

        return str(peak_load)

    def get_hourly_factors(
        self, gain_type: str, room_type: str = ""
    ) -> tuple[str, ...]:
        """Get the 24 hourly factors."""
        row = self.get_row(gain_type, room_type)

        return tuple(row[f"H{hour:02d}"] for hour in range(24))

    def get_n_people(self, room_type: str, n_bedrooms: int) -> str:
        """Get the number of people."""
        row = self.get_row("occupancy", room_type)

        n_people = int(row["n_people"])
        if room_type in N_BEDROOMS_DEPENDENT_ROOM_TYPES:
            n_people *= n_bedrooms

        return str(n_people)

    def get_sensible_frac(self, room_type: str) -> str:
        """Get the sensible fraction of occupants' metabolic rate."""
        row = self.get_row("occupancy", room_type)

        sensible_frac = int(row["peak_sensible"]) / (
            int(row["peak_sensible"]) + int(row["peak_latent"])
        )

        return str(round(sensible_frac, 7))


INTERNAL_GAIN_PROFILES = InternalGainProfiles()
