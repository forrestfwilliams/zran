from posix.types cimport off_t
from libc.stdio cimport FILE
from cython import ptrdiff_t

cdef extern from "zran.h":

    ctypedef struct point_t:
        off_t outloc "out"
        off_t inloc "in"
        int bits
        unsigned char window[32768]

    cdef struct deflate_index:
        int have
        int mode
        off_t length
        point_t *list

    int deflate_index_build(FILE *infile, off_t span, deflate_index **built)
    void deflate_index_free(deflate_index *index);
