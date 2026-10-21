"""Manipulate EnergyPlus EMS programs and calling managers."""

from typing import TYPE_CHECKING

import aark.ep.obj
from aark.ep.field import MAX_EP_STR_FIELD_LEN

if TYPE_CHECKING:
    from eppy.modeleditor import IDF


def add_program(idf: IDF, program_obj_name: str, *program_lines: str) -> None:
    """Add a program."""
    for line in program_lines:
        if len(line) > MAX_EP_STR_FIELD_LEN:
            raise ValueError(
                f"EMS program line exceeds the IDF string length limit: {line}."
            )

    aark.ep.obj.add(
        idf,
        "EnergyManagementSystem:Program",
        Name=program_obj_name,
        **{f"Program_Line_{i}": line for i, line in enumerate(program_lines, start=1)},
    )


def add_program_to_calling_manager(
    idf: IDF, calling_manager_obj_name: str, calling_point: str, program_obj_name: str
) -> None:
    """Add a program to a shared calling manager."""
    calling_manager_cls_name = "EnergyManagementSystem:ProgramCallingManager"

    if aark.ep.obj.has_named(idf, calling_manager_cls_name, calling_manager_obj_name):
        calling_manager_obj = aark.ep.obj.get_named(
            idf, calling_manager_cls_name, calling_manager_obj_name
        )

        if calling_manager_obj.EnergyPlus_Model_Calling_Point != calling_point:
            raise ValueError(
                f"Program calling manager exists at a different calling point: {calling_manager_obj.EnergyPlus_Model_Calling_Point}."
            )

        aark.ep.obj.rstrip(calling_manager_obj)
        n_programs = len(calling_manager_obj.fieldvalues) - 3
        if not any(
            calling_manager_obj[f"Program_Name_{i}"] == program_obj_name
            for i in range(1, n_programs + 1)
        ):
            calling_manager_obj[f"Program_Name_{n_programs + 1}"] = program_obj_name
    else:
        aark.ep.obj.add(
            idf,
            calling_manager_cls_name,
            Name=calling_manager_obj_name,
            EnergyPlus_Model_Calling_Point=calling_point,
            Program_Name_1=program_obj_name,
        )
