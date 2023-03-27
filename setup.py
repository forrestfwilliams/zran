#!/usr/bin/env python
"""Setup script for zran package.

This script was modified from the setup.py file created by
Paul McCarthy for the indexed_gzip project. You can find the
project at this link: https://github.com/pauldmccarthy/indexed_gzip.
"""

import glob
import os
import os.path as op

from setuptools import Extension, setup

# compile ZLIB source?
ZLIB_HOME = os.environ.get("ZLIB_HOME", None)

# If cython is present, we'll compile
# the pyx files from scratch. Otherwise,
# we'll compile the pre-generated c
# files (which are assumed to be present).
have_cython = True

try:
    from Cython.Build import cythonize
except Exception:
    have_cython = False

print(
    f'''zran setup
    have_cython: {have_cython} (if True, modules will be cythonized, else cythonized C files are assumed to be present)
    ZLIB_HOME:   {ZLIB_HOME} (if set, ZLIB sources are compiled into the indexed_gzip extension)
'''
)

# compile flags
include_dirs = []
lib_dirs = []
libs = []
extra_srcs = []
extra_compile_args = []
compiler_directives = {'language_level': 3}
define_macros = []

if ZLIB_HOME is not None:
    include_dirs.append(ZLIB_HOME)
    extra_srcs.extend(glob.glob(op.join(ZLIB_HOME, '*.c')))
else:
    # if ZLIB_HOME is set, statically link,
    # rather than use system-provided zlib
    libs.append('z')
    extra_compile_args += ['-Wall', '-Wno-unused-function']

# Compile from cython files if
# possible, or compile from c.
if have_cython:
    pyx_ext = 'pyx'
else:
    pyx_ext = 'c'

# The zran module
zran_ext = Extension(
    'zran',
    [op.join('src', 'zran', 'zranlib.{}'.format(pyx_ext)), op.join('src', 'zran', 'zran.c')] + extra_srcs,
    libraries=libs,
    library_dirs=lib_dirs,
    include_dirs=include_dirs,
    extra_compile_args=extra_compile_args,
    define_macros=define_macros,
)
extensions = [zran_ext]

# Cythonize if we can
if have_cython:
    extensions = cythonize(extensions, compiler_directives=compiler_directives)

setup(ext_modules=extensions)
