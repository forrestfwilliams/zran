# vim: filetype=python
import struct as py_struct
import zlib
import warnings
from collections import namedtuple
from operator import attrgetter
from typing import Iterable, List

import cython
from cython.cimports import zran
from cython.cimports.cpython.bytes import PyBytes_AsString, PyBytes_Size
from cython.cimports.cpython.mem import PyMem_Free, PyMem_Malloc
from cython.cimports.libc.stdio import fclose
from cython.cimports.libc.stdlib import malloc
from cython.cimports.posix.stdio import fmemopen
from cython.cimports.posix.types import off_t

WINDOW_LENGTH = 32768
GZ_WBITS = 31
Point = namedtuple("Point", "outloc inloc bits window")


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~Cython Functionality~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
class ZranError(Exception):
    pass


def check_for_error(return_code):
    error_codes = {
        "Z_ERRNO": -1,
        "Z_STREAM_ERROR": -2,
        "Z_DATA_ERROR": -3,
        "Z_MEM_ERROR": -4,
        "Z_BUF_ERROR": -5,
        "Z_VERSION_ERROR": -6,
    }

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
            raise ZranError("zran: failed with Z_STREAM_ERROR")
        else:
            raise ZranError(f"zran: failed with error code {return_code}")


@cython.cclass
class WrapperDeflateIndex:
    _ptr: cython.pointer(zran.deflate_index)
    ptr_owner: cython.bint

    def __cinit__(self):
        self.ptr_owner = False

    def __dealloc__(self):
        if self._ptr is not cython.NULL and self.ptr_owner is True:
            zran.deflate_index_free(self._ptr)
            self._ptr = cython.NULL

    def __init__(self):
        raise TypeError("This class cannot be instantiated directly")

    @property
    def have(self):
        return self._ptr.have if self._ptr is not cython.NULL else None

    @property
    def mode(self):
        return self._ptr.mode if self._ptr is not cython.NULL else None

    @property
    def length(self):
        return self._ptr.length if self._ptr is not cython.NULL else None

    @property
    def points(self):
        if self._ptr is not cython.NULL:
            result = []
            for i in range(self.have):
                point = Point(
                    self._ptr.list[i].outloc,
                    self._ptr.list[i].inloc,
                    self._ptr.list[i].bits,
                    self._ptr.list[i].window[:WINDOW_LENGTH],
                )
                result.append(point)
        else:
            result = None
        return result

    @staticmethod
    @cython.cfunc
    def from_ptr(_ptr: cython.pointer(zran.deflate_index), owner: cython.bint = False) -> WrapperDeflateIndex:  # noqa
        wrapper = cython.declare(WrapperDeflateIndex, WrapperDeflateIndex.__new__(WrapperDeflateIndex))
        wrapper._ptr = _ptr
        wrapper.ptr_owner = owner
        return wrapper

    @staticmethod
    @cython.cfunc
    def from_python_index(mode: int, length: int, have: int, points: List[Point]):
        # Can't use PyMem_Malloc here because free operation is controlled by C library
        _new_ptr = cython.declare(
            cython.pointer(zran.deflate_index),
            cython.cast(cython.pointer(zran.deflate_index), malloc(cython.sizeof(zran.deflate_index))),
        )
        if _new_ptr is cython.NULL:
            raise MemoryError

        _new_ptr.have = have
        _new_ptr.mode = mode
        _new_ptr.length = length

        # Can't use PyMem_Malloc here because free operation is controlled by C library
        list_size = have * cython.sizeof(zran.point_t)
        _new_ptr.list = cython.cast(cython.pointer(zran.point_t), malloc(list_size))

        if _new_ptr.list is cython.NULL:
            raise MemoryError

        for i in range(have):
            _new_ptr.list[i].outloc = points[i].outloc
            _new_ptr.list[i].inloc = points[i].inloc
            _new_ptr.list[i].bits = points[i].bits
            _new_ptr.list[i].window = points[i].window

        return WrapperDeflateIndex.from_ptr(_new_ptr, owner=True)


def build_deflate_index(input_bytes: bytes, span: off_t = 2**20) -> WrapperDeflateIndex:
    compressed_data = cython.declare(cython.p_char, PyBytes_AsString(input_bytes))
    compressed_data_length = cython.declare(off_t, PyBytes_Size(input_bytes))
    infile = fmemopen(compressed_data, compressed_data_length, b"r")

    built = cython.declare(cython.pointer(zran.deflate_index))

    rtc = zran.deflate_index_build(infile, span, cython.address(built))
    fclose(infile)
    check_for_error(rtc)
    index = WrapperDeflateIndex.from_ptr(built, owner=True)
    return index


def decompress(input_bytes: bytes, index: Index, offset: off_t, length: int) -> bytes:  # noqa
    # first_bit_zero = index.points[0].bits == 0
    # if index.have > 1:
    #     offset_before_second_point = offset < index.points[1].outloc
    # else:
    #     offset_before_second_point = False

    # if not first_bit_zero and offset_before_second_point:
    #     raise ValueError(
    #         'When first index bit != 0, offset must be at or after second index point'
    #         f' ({index.points[1].outloc} for this index)'
    #     )

    # if offset + length > index.uncompressed_size:
    #     raise ValueError('Offset and length specified would result in reading past the file bounds')

    compressed_data = cython.declare(cython.p_char, PyBytes_AsString(input_bytes))
    compressed_data_length = cython.declare(off_t, PyBytes_Size(input_bytes))
    infile = fmemopen(compressed_data, compressed_data_length, b"r")

    rebuilt_index = cython.declare(WrapperDeflateIndex, index.to_c_index())
    uncompressed_data_length = (length + 1) * cython.sizeof(cython.uchar)
    data = cython.declare(cython.p_uchar, cython.cast(cython.p_uchar, PyMem_Malloc(uncompressed_data_length)))
    rtc_extract = zran.deflate_index_extract(infile, rebuilt_index._ptr, offset, data, length)

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


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~Python Functionality~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#


class Index:
    def __init__(self, mode: int, compressed_size: int, uncompressed_size: int, have: int, points: Iterable[Point]):
        self.compressed_size = compressed_size
        self.uncompressed_size = uncompressed_size
        self.mode = mode
        self.have = have
        self.points = points

    @staticmethod
    def create_index(input_bytes: bytes, span: int = 2**20):
        c_index = build_deflate_index(input_bytes, span=span)
        new_index = Index(c_index.mode, len(input_bytes), c_index.length, c_index.have, c_index.points)
        del c_index
        return new_index

    def create_index_file(self):
        header = b"DFLIDX" + py_struct.pack("<iQQI", self.mode, self.compressed_size, self.uncompressed_size, self.have)
        sorted_points = sorted(self.points, key=attrgetter("outloc"))
        point_data = [py_struct.pack("<QQB", x.outloc, x.inloc, x.bits) for x in sorted_points]
        window_data = [x.window for x in sorted_points]
        dflidx = header + b"".join(point_data) + b"".join(window_data)

        compress_obj = zlib.compressobj(wbits=GZ_WBITS)
        compressed_dflidx = compress_obj.compress(dflidx)
        compressed_dflidx += compress_obj.flush()
        return compressed_dflidx

    def write_file(self, filename: str):
        with open(filename, "wb") as f:
            f.write(self.create_index_file())

    @staticmethod
    def parse_index_file(compressed_dflidx: bytes):
        decompress_obj = zlib.decompressobj(GZ_WBITS)
        dflidx = decompress_obj.decompress(compressed_dflidx)

        header_length = 30
        point_length = 17
        mode, compressed_size, uncompressed_size, have = py_struct.unpack("<iQQI", dflidx[6:header_length])
        point_end = header_length + (have * point_length)

        loc_data = []
        window_data = []
        for i in range(have):
            loc_bytes = dflidx[header_length + (i * point_length) : header_length + ((i + 1) * point_length)]
            loc_data.append(py_struct.unpack('<QQB', loc_bytes))

            window_bytes = dflidx[point_end + (WINDOW_LENGTH * i) : point_end + (WINDOW_LENGTH * (i + 1))]
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

    def create_modified_index(self, locations, end_location=None):
        """Modifies a set of access Points so that they only contain the needed data
        Args:
            locations: A list of uncompressed locations to be included in the new index.
                       The closes point before each location will be selected.
            end_location: The uncompressed endpoint of the index. Used to determine file size.

        Returns:
            range of compressed data, range of uncompressed data, a modified Index.
        """
        max_uncompressed_offset = self.points[-1].outloc
        if not end_location or end_location > max_uncompressed_offset:
            outloc_end = self.uncompressed_size
            inloc_end = self.compressed_size
        else:
            endpoint = get_closest_point(self.points, end_location, greater_than=True)
            outloc_end = endpoint.outloc
            inloc_end = endpoint.inloc

        start_points = [get_closest_point(self.points, x) for x in locations]
        desired_points = sorted(start_points, key=attrgetter("outloc"))

        compressed_range = [desired_points[0].inloc, inloc_end]
        uncompressed_range = [desired_points[0].outloc, outloc_end]

        inloc_offset = desired_points[0].inloc - self.points[0].inloc
        outloc_offset = desired_points[0].outloc

        # to account for nonzero first point.bits
        if desired_points[0].outloc != self.points[0].outloc:
            compressed_range[0] -= 1
            inloc_offset -= 1

        output_points = []
        for point in desired_points:
            new_point = Point(point.outloc - outloc_offset, point.inloc - inloc_offset, point.bits, point.window)
            output_points.append(new_point)

        modified_index = Index(
            self.mode,
            compressed_range[1] - compressed_range[0],
            uncompressed_range[1] - uncompressed_range[0],
            len(output_points),
            output_points,
        )
        return compressed_range, uncompressed_range, modified_index


def get_closest_point(points, value, greater_than=False):
    """Identifies index of closest value in a numpy array to input value.
    Args:
        points: iteratable of point namedtuples
        value: value that you want to find closest index for in array
        greater_than: whether to return closest Point that is <= or > value
    Returns:
        closest Point
    """
    sorted_points = sorted(points, key=attrgetter("outloc"))

    closest = 0
    for i in range(len(sorted_points)):
        if sorted_points[i].outloc <= value and sorted_points[i].outloc > sorted_points[closest].outloc:
            closest = i

    if greater_than:
        closest += 1
        closest = min(closest, len(sorted_points) - 1)

    return sorted_points[closest]
