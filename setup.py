#!/usr/bin/env python
"""Setup script for zran package.
"""

import sys
import os
import glob
import os.path as op

from setuptools import setup
from setuptools import Extension


# Platform information
python2   = sys.version_info[0] == 2
noc99     = python2 or (sys.version_info[0] == 3 and sys.version_info[1] <= 4)
windows   = sys.platform.startswith("win")
testing   = 'INDEXED_GZIP_TESTING' in os.environ

# compile ZLIB source?
ZLIB_HOME = os.environ.get("ZLIB_HOME", None)

# If cython is present, we'll compile
# the pyx files from scratch. Otherwise,
# we'll compile the pre-generated c
# files (which are assumed to be present).
have_cython = True
have_numpy  = True

try:
    from Cython.Build import cythonize
except Exception:
    have_cython = False

# We need numpy to compile the test modules
try:
    import numpy as np
except Exception:
    have_numpy = False

print('zran setup')
print('  have_cython: {} (if True, modules will be cythonized, '
      'otherwise pre-cythonized C files are assumed to be '
      'present)'.format(have_cython))
print('  have_numpy:  {} (if True, test modules will '
      'be compiled)'.format(have_numpy))
print('  ZLIB_HOME:   {} (if set, ZLIB sources are compiled into '
      'the indexed_gzip extension)'.format(ZLIB_HOME))


# compile flags
include_dirs        = []
lib_dirs            = []
libs                = []
extra_srcs          = []
extra_compile_args  = []
compiler_directives = {'language_level' : 2}
define_macros       = []

if ZLIB_HOME is not None:
    include_dirs.append(ZLIB_HOME)
    extra_srcs.extend(glob.glob(op.join(ZLIB_HOME, '*.c')))

# If numpy is present, we need
# to include the headers
if have_numpy:
    include_dirs.append(np.get_include())

if windows:
    if ZLIB_HOME is None:
        libs.append('zlib')

    # For stdint.h which is not included in the old Visual C
    # compiler used for Python 2
    if python2:
        include_dirs.append('compat')

    # Some C functions might not be present when compiling against
    # older versions of python
    if noc99:
        extra_compile_args += ['-DNO_C99']

# linux / macOS
else:
    # if ZLIB_HOME is set, statically link,
    # rather than use system-provided zlib
    if ZLIB_HOME is None:
        libs.append('z')
    extra_compile_args += ['-Wall', '-Wno-unused-function']

if testing:
    compiler_directives['linetrace'] = True
    define_macros += [('CYTHON_TRACE_NOGIL', '1')]

# Compile from cython files if
# possible, or compile from c.
if have_cython: pyx_ext = 'pyx'
else:           pyx_ext = 'c'

# The indexed_gzip module
igzip_ext = Extension(
    'zran',
    [op.join('zran', 'zranlib.{}'.format(pyx_ext)),
     op.join('zran', 'zran.c')] + extra_srcs,
    libraries=libs,
    library_dirs=lib_dirs,
    include_dirs=include_dirs,
    extra_compile_args=extra_compile_args,
    define_macros=define_macros)
print(igzip_ext)
extensions = [igzip_ext]

# Cythonize if we can
if have_cython:
    extensions = cythonize(extensions, compiler_directives=compiler_directives)

setup(
    name='zran',
    packages=['zran'],
    author='Forrest Williams',
    author_email='ffwilliams2@alaska.edu',
    description='Fast random access of zlib compressed files in Python',
    url='https://github.com/forrestfwilliams/zran',
    license='zlib',

    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: zlib/libpng License',
        'Programming Language :: C',
        'Programming Language :: Cython',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
        'Topic :: System :: Archiving :: Compression',
    ],
    ext_modules=extensions,
)
