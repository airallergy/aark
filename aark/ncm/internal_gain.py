"""NCM internal gain profiles."""

import math
from typing import TYPE_CHECKING

import aark._utils
import aark.ep._pact
import aark.ep.obj
import aark.ep.sched
import aark.ncm._utils
from aark._utils import YEAR_END_MONTH_DAY, YEAR_START_MONTH_DAY
from aark.ncm.data import ACTIVITY_DATABASE

if TYPE_CHECKING:
    from eppy.modeleditor import IDF

    from aark._utils import MonthDay
    from aark.ncm._utils import ActivityMap


def _add_occupancy(
    idf: IDF,
    zone_name: str,
    activity_name: str,
    start_month_day: MonthDay,
    end_month_day: MonthDay,
) -> None:
    """Add occupancy gain to one zone."""
    # get ncm data
    occupancy = ACTIVITY_DATABASE.get_occupancy(activity_name)
    daily_scheds, weekly_scheds, annual_scheds = ACTIVITY_DATABASE.get_sched(
        occupancy["sched_name"]
    )

    # get object names
    metabolic_sched_obj_name = aark.ncm._utils.sched_uid("metabolic", activity_name)
    gain_obj_name = aark.ncm._utils.gain_uid("occupancy", zone_name)

    # add schedule objects
    aark.ncm._utils.add_scheds(
        idf,
        daily_scheds,
        weekly_scheds,
        annual_scheds,
        "Fraction",
        start_month_day,
        end_month_day,
    )
    aark.ep.sched.add_constant_obj(
        idf, metabolic_sched_obj_name, "Metabolism", occupancy["metabolic_rate"]
    )

    # add the occupancy gain object
    aark.ep.obj.add(
        idf,
        "People",
        Name=gain_obj_name,
        Zone_or_ZoneList_or_Space_or_SpaceList_Name=zone_name,
        Number_of_People_Schedule_Name=aark.ncm._utils.prefix(occupancy["sched_name"]),
        Number_of_People_Calculation_Method="People/Area",
        People_per_Floor_Area=occupancy["density"],
        Sensible_Heat_Fraction=occupancy["sensible_frac"],
        Activity_Level_Schedule_Name=metabolic_sched_obj_name,
    )


def _add_equipment(
    idf: IDF,
    zone_name: str,
    activity_name: str,
    start_month_day: MonthDay,
    end_month_day: MonthDay,
) -> None:
    """Add equipment gain to one zone."""
    # get ncm data
    equipment = ACTIVITY_DATABASE.get_equipment(activity_name)
    daily_scheds, weekly_scheds, annual_scheds = ACTIVITY_DATABASE.get_sched(
        equipment["sched_name"]
    )

    # get object names
    gain_obj_name = aark.ncm._utils.gain_uid("equipment", zone_name)

    # add schedule objects
    aark.ncm._utils.add_scheds(
        idf,
        daily_scheds,
        weekly_scheds,
        annual_scheds,
        "Fraction",
        start_month_day,
        end_month_day,
    )

    # add the gain object
    aark.ep.obj.add(
        idf,
        "ElectricEquipment",
        Name=gain_obj_name,
        Zone_or_ZoneList_or_Space_or_SpaceList_Name=zone_name,
        Schedule_Name=aark.ncm._utils.prefix(equipment["sched_name"]),
        Design_Level_Calculation_Method="Watts/Area",
        Watts_per_Floor_Area=equipment["power_density"],
        Fraction_Latent=equipment["latent_frac"],
    )


def _add_lighting(
    idf: IDF,
    zone_name: str,
    activity_name: str,
    luminous_efficacy: float,
    start_month_day: MonthDay,
    end_month_day: MonthDay,
) -> None:
    """Add lighting gain to one zone."""
    # get ncm data
    lighting = ACTIVITY_DATABASE.get_lighting(activity_name, luminous_efficacy)
    daily_scheds, weekly_scheds, annual_scheds = ACTIVITY_DATABASE.get_sched(
        lighting["sched_name"]
    )

    # get object names
    gain_obj_name = aark.ncm._utils.gain_uid("lighting", zone_name)

    # add schedule objects
    aark.ncm._utils.add_scheds(
        idf,
        daily_scheds,
        weekly_scheds,
        annual_scheds,
        "Fraction",
        start_month_day,
        end_month_day,
    )

    # add the gain object
    aark.ep.obj.add(
        idf,
        "Lights",
        Name=gain_obj_name,
        Zone_or_ZoneList_or_Space_or_SpaceList_Name=zone_name,
        Schedule_Name=aark.ncm._utils.prefix(lighting["sched_name"]),
        Design_Level_Calculation_Method="Watts/Area",
        Watts_per_Floor_Area=lighting["power_density"],
    )


def apply(
    idf: IDF,
    zone_map: ActivityMap,
    luminous_efficacy: float,
    start_month_day: MonthDay = YEAR_START_MONTH_DAY,
    end_month_day: MonthDay = YEAR_END_MONTH_DAY,
) -> None:
    """Apply internal gain profiles to the IDF.

    Load `aark.ncm.data.ACTIVITY_DATABASE` with `load(cur)` before calling.

    Parameters
    ----------
    idf : IDF
        IDF to receive internal gain profiles.
    zone_map : ActivityMap
        NCM activity names mapped to names of one or more `Zone` objects in `idf`. For
        example:

        ```python
        {
            "Dwell_DomBed": ["bedroom_1", "bedroom_2"],
            "Dwell_DomLounge": ["lounge"],
        }
        ```
    luminous_efficacy : float
        Lighting luminous efficacy in lm W-1. Power density is `LIGHTING_LUX /
        luminous_efficacy`, assuming utilisation and maintenance factors of one.
    start_month_day, end_month_day : MonthDay, optional
        Inclusive active period as `(month, day)` pairs, defaulting to the whole year. A
        start after the end spans New Year. For design and custom days, see 'Notes'.

    Notes
    -----
    Design and custom days use the following constant values, independently of
    the active period.

    | Profile   | Winter design day | Summer design day | Custom days |
    | --------- | ----------------- | ----------------- | ----------- |
    | Occupancy | Zero              | Full              | Zero        |
    | Lighting  | Zero              | Full              | Zero        |
    | Equipment | Zero              | Full              | Zero        |
    """
    # validate aark requirements
    aark.ep._pact.validate_ep_ver(idf)

    # validate user inputs
    aark.ncm._utils.validate_zone_map(idf, zone_map)
    _validate_luminous_efficacy(luminous_efficacy)
    aark._utils.validate_month_days(start_month_day, end_month_day)

    # apply gains to each zone
    for activity_name, zone_names in zone_map.items():
        for zone_name in zone_names:
            _add_occupancy(
                idf, zone_name, activity_name, start_month_day, end_month_day
            )

            _add_equipment(
                idf, zone_name, activity_name, start_month_day, end_month_day
            )

            _add_lighting(
                idf,
                zone_name,
                activity_name,
                luminous_efficacy,
                start_month_day,
                end_month_day,
            )


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------


def _validate_luminous_efficacy(luminous_efficacy: float) -> None:
    """Validate that luminous efficacy is finite and positive."""
    if not math.isfinite(luminous_efficacy) or luminous_efficacy <= 0:
        raise ValueError(
            f"Luminous efficacy must be finite and positive: {luminous_efficacy}."
        )
