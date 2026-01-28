# Copyright 2009-2018 Canonical Ltd.  All rights reserved.
#
# This file is part of wadllib
#
# wadllib is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# wadllib is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public
# License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with wadllib.  If not, see <http://www.gnu.org/licenses/>.

"""Test harness."""

__all__ = [
    'load_tests',
    ]

import __future__
import atexit
from contextlib import ExitStack
import doctest

try:
    import importlib.resources as importlib_resources
    importlib_resources.files  # missing on Python 3.8
except (ImportError, AttributeError):
    import importlib_resources


DOCTEST_FLAGS = (
    doctest.ELLIPSIS |
    doctest.NORMALIZE_WHITESPACE |
    doctest.REPORT_NDIFF)


def load_tests(loader, tests, pattern):
    doctest_files = []
    stack = ExitStack()
    atexit.register(stack.close)
    docs_resources = importlib_resources.files('wadllib').joinpath('docs')
    if docs_resources.is_dir():
        for resource in docs_resources.iterdir():
            if resource.name.endswith('.rst'):
                doctest_files.append(str(stack.enter_context(
                    importlib_resources.as_file(resource))))
    globs = {
        future_item: getattr(__future__, future_item)
        for future_item in ('absolute_import', 'print_function')}
    kwargs = dict(
        module_relative=False, globs=globs, optionflags=DOCTEST_FLAGS)
    tests.addTest(doctest.DocFileSuite(*doctest_files, **kwargs))
    return tests
