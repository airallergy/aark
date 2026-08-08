"""Technical Memorandum 59 2017 (TM59:2017): https://www.cibse.org/knowledge-research/knowledge-portal/technical-memorandum-59-design-methodology-for-the-assessment-of-overheating-risk-in-homes.

Nomenclature
------------
Trm
    Exponentially weighted running mean outdoor air temperature, degrees
    Celsius.
Top
    Indoor operative temperature, degrees Celsius.
Ta
    Indoor air temperature, degrees Celsius.

Notes
-----
The following modelling assumptions are used by `aark` but not explicitly specified by
TM59:

- The lighting gain is applied to all rooms by floor area, including non-habitable rooms
  with neither people nor equipment gain, such as bathrooms and halls.
- Intra-dwelling doors are open when occupants are awake and closed otherwise. All other
  doors are closed.
- Window opening requires the room to be occupied and its occupants to be awake.
- Available windows are fully open above 22 °C and fully closed otherwise.
- The sleeping period is 23:00 - 08:00 in line with the internal gain profiles; the
  22:00 - 07:00 period in criterion (b) is treated as a typo.
"""
