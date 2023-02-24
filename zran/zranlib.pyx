from posix.types cimport off_t
import cython
from libc.stdlib  cimport free, malloc
from libc.stdio cimport FILE, fopen, fclose
cimport czran


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
                result.append(self._ptr.list[i])
        else:
            result = None
        return result

    @staticmethod
    cdef WrapperDeflateIndex from_ptr(czran.deflate_index *_ptr, bint owner=False):
        cdef WrapperDeflateIndex wrapper = WrapperDeflateIndex.__new__(WrapperDeflateIndex)
        wrapper._ptr = _ptr
        wrapper.ptr_owner = owner
        return wrapper


def build_deflate_index(str filename, off_t span = 2**20):
    cdef FILE *infile = fopen(filename.encode(), b"rb")
    cdef czran.deflate_index *built
    rtc = czran.deflate_index_build(infile, span, &built)
    fclose(infile)
    try:
        index = WrapperDeflateIndex.from_ptr(built)
    except:
        czran.deflate_index_free(built)

    return index


def extract_data(str filename, off_t offset, off_t length, off_t span = 2**20):
    cdef FILE *infile = fopen(filename.encode(), b"rb")

    cdef czran.deflate_index *built
    cdef unsigned char* data = <unsigned char *> malloc((length + 1) * sizeof(char))

    try:
        rtc1 = czran.deflate_index_build(infile, span, &built)
        rtc2 = czran.deflate_index_extract(infile, built, offset, data, length)
        python_data = data[:length]
    finally:
        # Deallocate C Objects
        czran.deflate_index_free(built)
        fclose(infile)
        free(data)

    return python_data

