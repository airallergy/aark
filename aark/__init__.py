"""airallergy's research kit.

Notes
-----
Checking the equality of IDF field values is complex, because alpha fields are generally
case insensitive and ignore leading and trailing whitespace, with some exceptions.
`eppy` does not handle this well. For simplicity and consistency, `aark` treats the
equality of field values as follows.

- Assumes a valid and internally consistent input IDF.

    - The IDF has no input errors when simulated.
    - For existing objects in the IDF where some reference others by name, the object
      names and their reference names are exactly equal in case and surrounding
      whitespace.
    - Object names in room maps exactly match their IDF object names in case and
      surrounding whitespace.

- Looks up field values in the input IDF considering case and surrounding whitespace.

    - Numeric values are compared using approximate equality, except for blank and
      automatic numeric values, which are compared exactly.
    - Alpha values are compared after removing surrounding whitespace.
    - Alpha comparison is case insensitive, unless the field is marked `retaincase` in
      the IDD.

- Deduplicates objects of the same class using exact equality when the same IDF
  instance remains in memory.

    - `aark` adds field values as strings.
    - If an IDF has objects added by `aark` and gets loaded by `eppy` again, `aark` may
      fail because `eppy` may parse numeric strings to floats or ints.

- Fails fast on field-related violations when validating an input IDF.

    - Only the first violation is reported in the error message.
"""

__version__ = "0.1.0"
