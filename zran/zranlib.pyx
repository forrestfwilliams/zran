from posix.types cimport off_t
import cython
from libc.stdlib  cimport free, malloc
from libc.stdio cimport FILE, fopen, fclose, fdopen
cimport czran
from collections import namedtuple
from operator import attrgetter
from cpython.mem cimport PyMem_Malloc, PyMem_Free
import struct as py_struct

WINDOW_LENGTH = 32768
Point = namedtuple("Point", "outloc inloc bits window")

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
        else:
            raise ZranError("zran: failed with error code %d".format(return_code))


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

    def to_file(self, filename):
        header = b"DFLIDX" + py_struct.pack("<IQI", self.mode, self.length, self.have)
        sorted_points = sorted(self.points, key=attrgetter("outloc"))
        point_data = [py_struct.pack("<QQB", x.outloc, x.inloc, x.bits) for x in sorted_points]
        window_data = [x.window for x in sorted_points]
        dflidx = header + b"".join(point_data) + b"".join(window_data)
        with open(filename, "wb") as f:
            f.write(dflidx)
    
    @staticmethod
    def parse_dflidx(dflidx: bytes):
        header_length = 22
        point_length = 17
        mode, length, have = py_struct.unpack("<IQI", dflidx[6:header_length])
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
        return mode, length, have, points

    @staticmethod
    def from_file(filename):
        with open(filename, "rb") as f:
            dflidx = f.read()
        mode, length, have, points = WrapperDeflateIndex.parse_dflidx(dflidx)
        
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


def build_deflate_index(fileobj, off_t span = 2**20):
    # cdef FILE *infile = fopen(filename.encode(), b"rb")
    if fileobj.mode != "rb":
        raise IOError("File object must be open read-binary (rb) mode.")

    infile = fdopen(fileobj.fileno(), b"rb")
    cdef czran.deflate_index *built
    
    rtc = czran.deflate_index_build(infile, span, &built)
    # fclose(infile)
    check_for_error(rtc)

    try:
        index = WrapperDeflateIndex.from_ptr(built, owner=True)
    except Exception as e:
        czran.deflate_index_free(built)
        raise e

    return index


def extract_data(str filename, str index_filename, off_t offset, int length):
    cdef FILE *infile = fopen(filename.encode(), b"rb")
    cdef WrapperDeflateIndex rebuilt_index = WrapperDeflateIndex.from_file(index_filename)
    cdef unsigned char* data = <unsigned char *>PyMem_Malloc((length + 1) * sizeof(char))
    
    rtc = czran.deflate_index_extract(infile, rebuilt_index._ptr, offset, data, length)
    fclose(infile)
    
    try:
        check_for_error(rtc)
        python_data = data[:length]
    finally:
        # Deallocate C Objects
        PyMem_Free(data)

    return python_data


def extract_data_with_tmp_index(str filename, off_t offset, off_t length, off_t span = 2**20):
    cdef FILE *infile = fopen(filename.encode(), b"rb")
    cdef czran.deflate_index *built
    cdef unsigned char* data = <unsigned char *>PyMem_Malloc((length + 1) * sizeof(char))
    
    rtc1 = czran.deflate_index_build(infile, span, &built)
    try:
        check_for_error(rtc1)
    except ZranError as e:
        czran.deflate_index_free(built)
        raise e

    rtc2 = czran.deflate_index_extract(infile, built, offset, data, length)
    fclose(infile)

    try:
        check_for_error(rtc2)
        python_data = data[:length]
    finally:
        # Deallocate C Objects
        czran.deflate_index_free(built)
        PyMem_Free(data)

    return python_data
