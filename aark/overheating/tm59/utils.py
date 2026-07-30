"""Utility functions shared by the TM59 module."""

import csv
import importlib.resources
from collections import Counter
from types import MappingProxyType
from typing import TYPE_CHECKING

import aark.ep.generic
from aark.overheating.tm59.data import misc

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from eppy.modeleditor import IDF

    type ZoneMap = Mapping[str, Sequence[str]]


# -----------------------------------------------------------------------------
# Internal gain profiles
# -----------------------------------------------------------------------------


class InternalGainProfiles:
    """Provide TM59 internal gain profiles."""

    __slots__ = ("rows",)

    rows: tuple[MappingProxyType[str, str], ...]

    def __init__(self) -> None:
        """Read the internal gain profiles."""
        resource = importlib.resources.files("aark.overheating.tm59").joinpath(
            "data", "internal_gain_profiles.csv"
        )

        with resource.open() as f:
            reader = csv.DictReader(f)
            self.rows = tuple(map(MappingProxyType, reader))

    def get_row(
        self, gain_type: str, room_type: str = "", n_bedrooms: int = -1
    ) -> Mapping[str, str]:
        """Get the row for the given gain type, room type and number of bedrooms."""
        (row,) = (
            row
            for row in self.rows
            if (row["gain_type"] == gain_type)
            and (row["room_type"] == room_type)
            and (row["n_bedrooms"] == (str(n_bedrooms) if n_bedrooms > 0 else ""))
        )
        return row

    def get_peak_load(
        self, gain_type: str, room_type: str = "", n_bedrooms: int = -1
    ) -> str:
        """Get the peak load, including latent load per person for occupancy."""
        row = self.get_row(gain_type, room_type, n_bedrooms)

        peak_load = int(row["peak_sensible"])

        if gain_type == "occupancy":
            # this is definitely an integer, `//` is used for typing purposes
            peak_load = (peak_load + int(row["peak_latent"])) // int(row["n_people"])

        return str(peak_load)

    def get_hourly_factors(
        self, gain_type: str, room_type: str = "", n_bedrooms: int = -1
    ) -> tuple[str, ...]:
        """Get the 24 hourly factors."""
        row = self.get_row(gain_type, room_type, n_bedrooms)

        return tuple(row[f"H{hour:02d}"] for hour in range(24))

    def get_n_people(self, room_type: str, n_bedrooms: int = -1) -> str:
        """Get the number of people."""
        row = self.get_row("occupancy", room_type, n_bedrooms)

        return row["n_people"]

    def get_sensible_frac(self, room_type: str, n_bedrooms: int = -1) -> str:
        """Get the sensible fraction of occupants' metabolic rate."""
        row = self.get_row("occupancy", room_type, n_bedrooms)

        sensible_frac = int(row["peak_sensible"]) / (
            int(row["peak_sensible"]) + int(row["peak_latent"])
        )

        return str(round(sensible_frac, 7))

    @classmethod
    def _uid(cls, *args: str) -> str:
        """Build a standard aark-generated uid."""
        uid = "_".join(("tm59", *(arg for arg in args if arg)))
        return aark.prefix(uid)

    @classmethod
    def gain_uid(cls, gain_type: str, zone_name: str) -> str:
        """Build the uid of a zone-specific internal gain."""
        return cls._uid(gain_type, zone_name)

    @classmethod
    def sched_uid(cls, sched_type: str, room_type: str = "") -> str:
        """Build the uid of an internal gain schedule."""
        return cls._uid(sched_type, room_type)


INTERNAL_GAIN_PROFILES = InternalGainProfiles()


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------


def validate_zone_map(zone_map: ZoneMap) -> None:
    """Validate the structure of a dwelling or communal corridor zone map."""
    # a zone map must not be empty
    if not zone_map:
        raise ValueError(f"Empty zone map: {zone_map}.")

    # check room types
    room_types = set(zone_map)

    # a room type must be contained in the misc data
    invalid_room_types = room_types - misc.ALL_ROOM_TYPES
    if invalid_room_types:
        raise ValueError(f"Invalid room types: {invalid_room_types}.")

    for zone_names in zone_map.values():
        # a zone name sequence must not be str or bytes
        if isinstance(zone_names, str):
            raise TypeError(f"Invalid zone sequence: {zone_names}.")

        if len(zone_names) == 0:
            raise ValueError(f"Empty zone sequence: {zone_names}.")

    if misc.COMMUNAL_CORRIDOR_TYPE in room_types:
        # a communal corridor must not co-exist with dwelling room types
        if room_types != {misc.COMMUNAL_CORRIDOR_TYPE}:
            raise ValueError(
                f"Mixed communal corridor and dwelling room types: {room_types}."
            )

    elif misc.STUDIO_TYPE in room_types:
        # a studio must not co-exist with other habitable room types
        if room_types - ({misc.STUDIO_TYPE} | misc.ANCILLARY_ROOM_TYPES):
            raise ValueError(
                f"Mixed studio and other habitable room types: {room_types}."
            )

        # a studio must not contain more than one studio zone
        studio_zone_names = zone_map[misc.STUDIO_TYPE]
        if len(studio_zone_names) > 1:
            raise ValueError(f"Multiple studios: {studio_zone_names}.")

    else:
        n_bedrooms = sum(
            len(zone_map.get(room_type, ())) for room_type in misc.BEDROOM_TYPES
        )

        if n_bedrooms == 0:
            raise ValueError(f"Missing bedrooms: {zone_map}.")

        if n_bedrooms > misc.MAX_TABULATED_N_BEDROOMS:
            raise ValueError(f"Too many bedrooms: {n_bedrooms}.")


def validate_zone_maps(idf: IDF, zone_maps: Sequence[ZoneMap]) -> None:
    """Validate all zone maps provided by users."""
    # validate the structure of each zone map
    for zone_map in zone_maps:
        validate_zone_map(zone_map)

    # get all zone names
    zone_names = [
        zone_name
        for zone_map in zone_maps
        for zone_names in zone_map.values()
        for zone_name in zone_names
    ]

    # all zone names must be unique across all zone maps
    duplicate_names = sorted(
        name for name, count in Counter(zone_names).items() if count > 1
    )
    if duplicate_names:
        raise ValueError(f"Duplicate zone names: {duplicate_names}.")

    # validate the existence of zone names in the idf
    aark.ep.generic.validate_zones_exist_by_name(idf, zone_names)


# -----------------------------------------------------------------------------
# Predication
# -----------------------------------------------------------------------------


def is_communal_corridor_zone_map(zone_map: ZoneMap) -> bool:
    """Return whether a zone map represents communal corridors."""
    return set(zone_map) == {misc.COMMUNAL_CORRIDOR_TYPE}
