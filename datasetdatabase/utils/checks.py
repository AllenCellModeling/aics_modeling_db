#!/usr/bin/env python

# installed
from typing import Union
import pathlib
import types

CHECK_TYPES_ERR = """

Allowed types: {a}
Given type: {g}
Given value: {v}
"""

CHECK_FILE_EXISTS_ERR = """

The provided filepath does not exist.
Given filepath: {f}
"""

CHECK_INGEST_ERR = """

Something besides insertion went wrong...
{e}
"""


def check_types(var,
                allowed: Union[type, list, tuple],
                err: str = CHECK_TYPES_ERR) -> \
                Union[bool, TypeError]:
    """
    Check the provided variable and enforce that it is one of the passed types.

    Example
    ==========
    ```
    >>> temp = "this is a string"
    >>> check_types(temp, str)
    True

    >>> check_types(temp, [str, int])
    True

    >>> check_types(temp, tuple([str, int]))
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
        A variable to be checked for type.
    allowed: type, list, tuple
        A single, list, or tuple of types to check the provided variable
        against.
    err: str
        An additional error message to be displayed before the standard error
        should the provided variable not pass type checks.

    Returns
    ==========
    is_type: bool
        Returns boolean True if the provided variable is of the provided
        type(s).

    Errors
    ==========
    TypeError:
        The provided variable was not one of the provided type(s).

    """

    # enforce types
    if not isinstance(err, str):
        raise TypeError(CHECK_TYPES_ERR.format(a=str, t=type(err), v=err))

    # convert to tuple if list passed
    if isinstance(allowed, list):
        allowed = tuple(allowed)

    # check types
    if isinstance(var, allowed):
        return True

    # format error
    if CHECK_TYPES_ERR not in err:
        err += CHECK_TYPES_ERR

    # raise error
    raise TypeError(err.format(a=allowed, t=type(var), v=var))


def check_file_exists(f: Union[str, pathlib.Path],
                      err: str =CHECK_FILE_EXISTS_ERR) -> \
                      Union[bool, FileNotFoundError]:
    """
    Check the provided filepath for existence.

    Example
    ==========
    ```
    >>> temp = "/this/does/exist.jpg"
    >>> check_file_exists(temp)
    True

    >>> temp = "/this/does/not/exist.jpg"
    >>> check_file_exists(temp)
    FileNotFoundError:

    The provided filepath does not exist.
    Given filepath: /this/does/not/exist.png

    >>> check_file_exists(temp, "this message displays first")
    FileNotFoundError: this message displays first

    The provided filepath does not exist.
    Given filepath: /this/does/not/exist.png

    ```

    Parameters
    ==========
    f: str, pathlib.Path
        A string or pathlib.Path filepath to be checked for existence.
    err: str
        An additional error message to be displayed before the standard error
        should the provided variable not pass existence checks.

    Returns
    ==========
    file_exists: bool
        Returns boolean True if the provided filepath does exist.

    Errors
    ==========
    FileNotFoundError:
        The provided filepath did not exist.

    """

    # enforce types
    check_types(f, [str, pathlib.Path])
    check_types(err, str)

    # convert
    f = pathlib.Path(f)

    # actual check
    if f.exists():
        return True

    # format error
    if CHECK_FILE_EXISTS_ERR not in err:
        err += CHECK_FILE_EXISTS_ERR

    # raise error
    raise FileNotFoundError(err.format(f=f))


def check_ingest_error(e: Exception, err: str = CHECK_INGEST_ERR) \
    -> Union[bool, TypeError]:
    """
    Check the provided exception and enforce that it was an ingestion error.

    Example
    ==========
    ```
    >>> e = QueryException("SQL: INSERT INTO...")
    >>> check_ingest_error(e)
    True

    >>> e = QueryException("SQL: INSERT INTO...")
    >>> check_ingest_error(e)
    TypeError:

    Something besides insertion went wrong...
    {Full Error}

    >>> check_ingest_error(e, "this message displays first")
    TypeError: this message displays first

    Something besides insertion went wrong...
    {Full Error}

    ```

    Parameters
    ==========
    e: Exception
        An error that needs to be checked for ingestion error.
    err: str
        An additional error message to be displayed before the standard error
        should the provided variable not pass type checks.

    Returns
    ==========
    was_ingest: bool
        Returns boolean True if the provided error was an insertion error.

    Errors
    ==========
    TypeError:
        The provided error was not an insertion error.

    """

    # enforce types
    check_types(err, str)

    if "SQL: INSERT INTO" in str(e):
        return True

    # format error
    if CHECK_FILE_EXISTS_ERR not in err:
        err += CHECK_FILE_EXISTS_ERR

    # raise error
    raise TypeError(err.format(e=e))
