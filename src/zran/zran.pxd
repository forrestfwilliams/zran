from posix.types cimport off_t
from libc.stdio cimport FILE
from cython import ptrdiff_t

cdef extern from "zran.h":

    ctypedef struct point_t:
        off_t outloc "out"  # offset in uncompressed data
        off_t inloc "in"  # offset in compressed file of first full byte
        int bits  # 0, or number of bits (1-7) from byte at in-1
        unsigned char window[32768]  # preceding 32K of uncompressed data

    cdef struct deflate_index:
        int have  # number of access points in list
        int mode  # -15 for raw, 15 for zlib, or 31 for gzip
        off_t length  # total length of uncompressed data
        point_t *list  # allocated list of access points

    int deflate_index_build(FILE *infile, off_t span, deflate_index **built)

    ptrdiff_t deflate_index_extract(FILE *infile, deflate_index *index, off_t offset, unsigned char *buf, size_t len)

    void deflate_index_free(deflate_index *index);
