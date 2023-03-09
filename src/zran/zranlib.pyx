from posix.types cimport off_t
from posix.stdio cimport fmemopen
import cython
from libc.stdlib  cimport free, malloc
from libc.stdio cimport FILE, fopen, fclose, fdopen
cimport czran
from collections import namedtuple
from typing import Iterable
from operator import attrgetter
from cpython.mem cimport PyMem_Malloc, PyMem_Free
import struct as py_struct
from cpython.bytes cimport PyBytes_AsString, PyBytes_Size

WINDOW_LENGTH = 32768
Point = namedtuple("Point", "outloc inloc bits window")

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~Cython Functionality~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
class ZranError(Exception):
    pass


def check_for_error(return_code):
    error_codes = {"Z_ERRNO": -1, "Z_STREAM_ERROR": -2, "Z_DATA_ERROR": -3, "Z_MEM_ERROR": -4,
                   "Z_BUF_ERROR": -5, "Z_VERSION_ERROR": -6}

    if return_code < 0:
        if return_code == error_codes["Z_MEM_ERROR"]:
            raise ZranError("zran: out of memory")
        elif return_code == error_codes["Z_BUF_ERROR"]:
            raise ZranError("zran: input file ended prematurely")
        elif return_code == error_codes["Z_DATA_ERROR"]:
            raise ZranError("zran: compressed data error in input file")
        elif return_code == error_codes["Z_ERRNO"]:
            raise ZranError("zran: read error on input file")
        elif return_code == error_codes["Z_STREAM_ERROR"]:
            raise ZranError(f"zran: failed with Z_STREAM_ERROR")
        else:
            raise ZranError(f"zran: failed with error code {return_code}")


cdef class WrapperDeflateIndex:
    cdef czran.deflate_index *_ptr
    cdef bint ptr_owner

    def __cinit__(self):
        self.ptr_owner = False

    def __dealloc__(self):
        if self._ptr is not NULL and self.ptr_owner is True:
            czran.deflate_index_free(self._ptr)
            self._ptr = NULL

    def __init__(self):
        raise TypeError("This class cannot be instantiated directly")

    @property
    def have(self):
        return self._ptr.have if self._ptr is not NULL else None

    @property
    def mode(self):
        return self._ptr.mode if self._ptr is not NULL else None

    @property
    def length(self):
        return self._ptr.length if self._ptr is not NULL else None

    @property
    def points(self):
        if self._ptr is not NULL:
            result = []
            for i in range(self.have):
                point = Point(self._ptr.list[i].outloc,
                              self._ptr.list[i].inloc,
                              self._ptr.list[i].bits,
                              self._ptr.list[i].window[:WINDOW_LENGTH]
                              )
                result.append(point)
        else:
            result = None
        return result

    @staticmethod
    cdef WrapperDeflateIndex from_ptr(czran.deflate_index *_ptr, bint owner=False):
        cdef WrapperDeflateIndex wrapper = WrapperDeflateIndex.__new__(WrapperDeflateIndex)
        wrapper._ptr = _ptr
        wrapper.ptr_owner = owner
        return wrapper

    @staticmethod
    def from_python_index(mode, length, have, points):
        # Can't use PyMem_Malloc here because free operation is controlled by C library
        cdef czran.deflate_index *_new_ptr = <czran.deflate_index *>malloc(sizeof(czran.deflate_index))
        if _new_ptr is NULL:
            raise MemoryError

        _new_ptr.have = have
        _new_ptr.mode = mode
        _new_ptr.length = length

        # Can't use PyMem_Malloc here because free operation is controlled by C library
        _new_ptr.list = <czran.point_t *>malloc(have * sizeof(czran.point_t))
        if _new_ptr.list is NULL:
            raise MemoryError

        for i in range(have):
            _new_ptr.list[i].outloc = points[i].outloc
            _new_ptr.list[i].inloc = points[i].inloc
            _new_ptr.list[i].bits = points[i].bits
            _new_ptr.list[i].window = points[i].window

        return WrapperDeflateIndex.from_ptr(_new_ptr, owner=True)


def build_deflate_index(bytes input_bytes, off_t span = 2**20):
    cdef char* compressed_data = PyBytes_AsString(input_bytes)
    cdef off_t compressed_data_length = PyBytes_Size(input_bytes)
    infile = fmemopen(compressed_data, compressed_data_length, b"r")

    cdef czran.deflate_index *built

    rtc = czran.deflate_index_build(infile, span, &built)
    fclose(infile)
    check_for_error(rtc)
    index = WrapperDeflateIndex.from_ptr(built, owner=True)
    return index


def decompress(bytes input_bytes, index, off_t offset, int length):
    cdef char* compressed_data = PyBytes_AsString(input_bytes)
    cdef off_t compressed_data_length = PyBytes_Size(input_bytes)
    infile = fmemopen(compressed_data, compressed_data_length, b"r")

    cdef WrapperDeflateIndex rebuilt_index = index.to_c_index()
    cdef unsigned char* data = <unsigned char *>PyMem_Malloc((length + 1) * sizeof(char))

    rtc_extract = czran.deflate_index_extract(infile, rebuilt_index._ptr, offset, data, length)

    try:
        check_for_error(rtc_extract)
        python_data = data[:length]
    except ZranError as e:
        raise e
    finally:
        # Deallocate C Objects
        fclose(infile)
        PyMem_Free(data)

    return python_data


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~Python Functionality~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#


class Index:
    def __init__(self, mode: int, compressed_size: int, uncompressed_size: int, have: int, points: Iterable[Point]):
        self.compressed_size = compressed_size
        self.uncompressed_size = uncompressed_size
        self.mode = mode
        self.have = have
        self.points = points

    @staticmethod
    def create_index(input_bytes: bytes, span: int = 2**20):
        c_index = build_deflate_index(input_bytes, span = 2**20)
        new_index = Index(c_index.mode, len(input_bytes), c_index.length, c_index.have, c_index.points)
        del c_index
        return new_index

    def create_index_file(self):
        header = b"DFLIDX" + py_struct.pack("<iQQI", self.mode, self.compressed_size, self.uncompressed_size, self.have)
        sorted_points = sorted(self.points, key=attrgetter("outloc"))
        point_data = [py_struct.pack("<QQB", x.outloc, x.inloc, x.bits) for x in sorted_points]
        window_data = [x.window for x in sorted_points]
        dflidx = header + b"".join(point_data) + b"".join(window_data)
        return dflidx

    def write_file(self, filename: str):
        with open(filename, "wb") as f:
            f.write(self.create_index_file())

    @staticmethod
    def parse_index_file(dflidx: bytes):
        header_length = 30
        point_length = 17
        mode, compressed_size, uncompressed_size, have = py_struct.unpack("<iQQI", dflidx[6:header_length])
        point_end = header_length + (have * point_length)

        loc_data = []
        window_data = []
        for i in range(have):
            i_next = i + 1
            loc_bytes = dflidx[header_length+(i*point_length) : header_length+((i+1)*point_length)]
            loc_data.append(py_struct.unpack('<QQB', loc_bytes))

            window_bytes = dflidx[point_end + (WINDOW_LENGTH * i) : point_end + (WINDOW_LENGTH * (i+1))]
            window_data.append(window_bytes)

        points = [Point(loc[0], loc[1], loc[2], window) for loc, window in zip(loc_data, window_data)]
        points = sorted(points, key=attrgetter("outloc"))
        return Index(mode, compressed_size, uncompressed_size, have, points)

    @staticmethod
    def read_file(filename: str):
        with open(filename, "rb") as f:
            new_index = Index.parse_index_file(f.read())
        return new_index

    def to_c_index(self):
        return WrapperDeflateIndex.from_python_index(self.mode, self.uncompressed_size, self.have, self.points)


def get_closest_point(points, value, greater_than = False):
    """Identifies index of closest value in a numpy array to input value.
    Args:
        points: iteratable of point namedtuples
        value: value that you want to find closes index for in array
        less_than: whether to return closest index that is <= or >= value
    Returns:
        closest point namedtuple
    """
    sorted_points = sorted(points, key=attrgetter("outloc"))

    closest = 0
    for i in range(len(sorted_points)):
        if sorted_points[i].outloc <= value and sorted_points[i].outloc > sorted_points[closest].outloc:
            closest = i

    if greater_than:
        closest += 1
        closest = min(closest, len(sorted_points)-1)

    return sorted_points[closest]


def modify_points(points, compressed_length, uncompressed_length, starts = [], stops = [], relative = True):
    """Modifies a set of access Points so that they only contain the needed data
    Args:
        points: list of Points needed to access a file with zran
        starts: uncompressed locations to provide indexes before
        stops: uncompressed locations to provide indexes after
    Returns:
        list of modified points
    """
    points = sorted(points, key=attrgetter("outloc"))
    first_value = points[0].inloc
    if starts or stops:
        start_points = list({get_closest_point(points, x) for x in starts})
        stop_points = list({get_closest_point(points, x, greater_than=True) for x in stops})
        desired_points = sorted(start_points + stop_points, key=attrgetter("outloc"))
    else:
        desired_points = points

    if desired_points[-1].inloc == max([x.inloc for x in points]):
        inloc_range = (desired_points[0].inloc, compressed_length)
    else:
        inloc_range = (desired_points[0].inloc, desired_points[-1].inloc)

    if desired_points[-1].outloc == max([x.outloc for x in points]):
        outloc_range = (desired_points[0].outloc, uncompressed_length)
    else:
        outloc_range = (desired_points[0].outloc, desired_points[-1].outloc)

    inloc_offset = 0
    outloc_offset = 0
    if relative:
        inloc_offset = desired_points[0].inloc - first_value
        outloc_offset = min([x.outloc for x in desired_points])
    desired_points = [Point(x.outloc - outloc_offset, x.inloc - inloc_offset, x.bits, x.window) for x in desired_points]

    return inloc_range, outloc_range, desired_points
