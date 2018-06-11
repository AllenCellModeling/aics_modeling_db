import pathlib
import os
import re

CHECK_TYPES_ERR = """

Allowed types: {p}
Given type: {t}
Given value: {v}
"""

CHECK_STRING_ERR = """

Allowed characters: {a}
Given characters: {g}
"""

CHECK_FILE_EXISTS_ERR = """

The provided filepath does not exist.
Given filepath: {f}
"""

def check_types(var, types, err=CHECK_TYPES_ERR):
    """
    Check the provided variable against the provided types given.

    Example
    ==========
    ```
    >>> temp = "this is a string"
    >>> check_types(temp, str)
    True
    >>> check_types(temp, [str, int])
    True
    >>> check_types(temp, tuple([str, dict]))
    True
    >>> check_types(temp, [int, list, dict])
    TypeError:

    Allowed types: (<class 'int'>, <class 'list'>, <class 'dict'>)
    Given type: <class 'str'>
    Given value: this is a string

    >>> check_types(temp, [int, list, dict], "this message displays first")
    TypeError: this message displays first

    Allowed types: (<class 'int'>, <class 'list'>, <class 'dict'>)
    Given type: <class 'str'>
    Given value: this is a string

    ```

    Parameters
    ==========
    var: object
        Any variable that's type should be checked.
    types: type, list, tuple
        A single type, a list of types, or a tuple of types to check the
        provided variable against.
    err: str
        An additional error message to be displayed before the standard error
        should the provided variable not pass type checks.

    Returns
    ==========
    is_type: bool
        Returns boolean True if the provided variable is of a type given.

    Errors
    ==========
    TypeError:
        The provided variable did not pass type checks.
    """

    # check err
    if not isinstance(err, str):
        raise TypeError(CHECK_TYPES_ERR.format(p=str, t=type(err), v=err))

    # convert to tuple if possible
    if isinstance(types, list):
        types = tuple(types)

    # check types
    if isinstance(var, types):
        return True

    # format error
    if err != CHECK_TYPES_ERR:
        err += CHECK_TYPES_ERR

    # raise error
    raise TypeError(err.format(p=types, t=type(var), v=var))

def check_string(seq, test, err=CHECK_STRING_ERR):
    """
    Check the provided string against the provided regex string.

    Example
    ==========
    ```
    >>> temp = "sequence"
    >>> check_string(temp, "^[a-zA-Z]+$")
    True
    >>> check_string(temp, "^[A-Z]+$")
    ValueError:

    Allowed characters: ^[A-Z]+$
    Given characters: sequence

    >>> check_string(temp, "^[A-Z]+$", "this message displays first")
    ValueError: this message displays first

    Allowed characters: ^[A-Z]+$
    Given characters: sequence

    ```

    Parameters
    ==========
    seq: str
        The sequence to be checked.
    test: str
        A regex string to be checked against.
    err: str
        An additional error message to be displayed before the standard error
        should the provided sequence not pass regex checks.

    Returns
    ==========
    is_allowed: bool
        Returns boolean True if the provided sequence passes regex string.

    Errors
    ==========
    ValueError:
        The provided sequence did not pass regex checks.
    """

    # enforce types
    check_types(seq, str)
    check_types(test, str)
    check_types(err, str)

    # actual check
    if re.match(test, seq):
        return True

    # format error
    if err != CHECK_STRING_ERR:
        err += CHECK_STRING_ERR

    # raise error
    raise ValueError(err.format(a=test, g=seq))

def check_file_exists(f, err=CHECK_FILE_EXISTS_ERR):
    """
    Check the provided filepath for existence.

    Example
    ==========
    ```
    >>> temp = "/this/does/exist.png"
    >>> check_file_exists(temp)
    True
    >>> temp = "/this/does/not/exist.png"
    >>> check_file_exists(temp)
    FileNotFoundError:

    The provided filepath does not exist.
    Given filepath: /this/does/not/exist.png

    ```

    Parameters
    ==========
    f: filepath
        Any filepath that should be checked for existence.
    err: str
        An additional error message to be displayed before the standard error
        should the provided variable not pass checks.

    Returns
    ==========
    exists: bool
        Returns boolean True if the provided filepath does exist.

    Errors
    ==========
    FileNotFoundError:
        The provided filepath did not pass checks.
    """

    # check types
    check_types(f, [str, pathlib.Path])
    check_types(err, str)

    # convert
    f = pathlib.Path(f)

    # actual check
    if os.path.exists(f):
        return True

    # format err
    if err != CHECK_FILE_EXISTS_ERR:
        err += CHECK_FILE_EXISTS_ERR

    # raise error
    raise FileNotFoundError(err.format(f=f))