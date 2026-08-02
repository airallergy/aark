"""Array utilities."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

    type Arr[
        ShapeT: tuple[int, *tuple[int, ...]] = tuple[int, *tuple[int, ...]],
        DTypeT: np.dtype = np.dtype[np.generic],
    ] = np.ndarray[ShapeT, DTypeT]
    type Arr2D[T: np.generic = np.generic] = Arr[tuple[int, int], np.dtype[T]]
    type FloatArr2D = Arr2D[np.floating]
