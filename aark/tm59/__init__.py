"""Technical Memorandum 59 2017 (TM59:2017): https://www.cibse.org/knowledge-research/knowledge-portal/technical-memorandum-59-design-methodology-for-the-assessment-of-overheating-risk-in-homes.

Nomenclature
------------

| Symbol | Unit | Definition                                                   |
| ------ | ---- | ------------------------------------------------------------ |
| `Trm`  | °C   | Exponentially weighted running mean outdoor air temperature. |
| `Top`  | °C   | Indoor operative temperature.                                |
| `Ta`   | °C   | Indoor air temperature.                                      |

Notes
-----
Use Greenwich Mean Time throughout the simulation, following the profile convention in
TM59:2017 Table 2. Disable daylight saving in the model and assess results on the same
time basis without a seasonal clock adjustment.

The following modelling assumptions are used by `aark` but not explicitly specified by
TM59:

- The lighting gain is applied to all rooms by floor area, including non-habitable rooms
  with neither people nor equipment gain, such as bathrooms and halls.
- Available windows are fully open above 22 °C and fully closed otherwise.
"""
