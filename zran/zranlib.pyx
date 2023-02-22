from posix.types cimport off_t
from libc.stdio cimport FILE, fopen, fclose
cimport czran

def build_deflate_index(str filename, off_t span):
    cdef FILE *infile = fopen(filename.encode(), b"rb")
    cdef czran.deflate_index *built
    rtn = czran.deflate_index_build(infile, span, &built)
    fclose(infile)
    czran.deflate_index_free(built)
    return 0
