import tempfile
from collections import namedtuple

import pytest

import zran

DFL_WBITS = -15
ZLIB_WBITS = 15
GZ_WBITS = 31

Offset = namedtuple('Offset', ['start', 'stop'])
offset_list = [
    Offset(start=109395, stop=149033895),
    Offset(start=595807395, stop=744731895),
    Offset(start=1191505395, stop=1340429895),
]


def test_create_index(compressed_gz_data):
    index = zran.Index.create_index(compressed_gz_data)

    assert index.mode == GZ_WBITS
    assert index.uncompressed_size > 0
    assert index.compressed_size == len(compressed_gz_data)
    assert index.have == 4

    points = index.points
    assert points[0].outloc == 0
    assert points[0].inloc == 10
    assert points[0].bits == 0
    assert len(points[0].window) == 32768


# @pytest.mark.skip(reason='Currently unstable. Will sometimes not fail if data has certain (unknown) properties')
def test_create_index_fail_head(data, compressed_gz_data_no_head):
    with pytest.raises(zran.ZranError, match='zran: compressed data error in input file'):
        zran.Index.create_index(compressed_gz_data_no_head)


# @pytest.mark.skip(reason='Currently unstable. Will sometimes not fail if data has certain (unknown) properties')
def test_create_index_fail_tail(data, compressed_gz_data_no_tail):
    with pytest.raises(zran.ZranError, match='zran: input file ended prematurely'):
        zran.Index.create_index(compressed_gz_data_no_tail)


@pytest.mark.parametrize('compressed_file', ['gz', 'dfl', 'zlib'], indirect=True)
def test_parse_index_file(compressed_file):
    index_file = tempfile.NamedTemporaryFile()

    index = zran.Index.create_index(compressed_file)
    index.write_file(index_file.name)
    new_index = zran.Index.read_file(index_file.name)

    assert index.mode == new_index.mode
    assert index.have == new_index.have
    assert index.compressed_size == new_index.compressed_size
    assert index.uncompressed_size == new_index.uncompressed_size
    assert len(index.points) == len(new_index.points)


@pytest.mark.parametrize('compressed_file', ['gz', 'dfl', 'zlib'], indirect=True)
def test_decompress(data, compressed_file):
    start = 100
    length = 1000
    index = zran.Index.create_index(compressed_file)
    test_data = zran.decompress(compressed_file, index, start, length)
    assert data[start : start + length] == test_data


# @pytest.mark.skip(reason='Currently unstable. Will sometimes not fail if data has certain (unknown) properties')
def test_decompress_fail(data, compressed_gz_data, compressed_gz_data_no_head):
    start = 100
    length = 1000
    index = zran.Index.create_index(compressed_gz_data)
    with pytest.raises(zran.ZranError, match='zran: compressed data error in input file'):
        zran.decompress(compressed_gz_data_no_head, index, start, length)


def test_get_closest_point():
    points = [zran.Point(0, 0, 0, b''), zran.Point(2, 0, 0, b''), zran.Point(4, 0, 0, b''), zran.Point(5, 0, 0, b'')]
    r1 = zran.get_closest_point(points, 3)
    assert r1.outloc == 2

    r2 = zran.get_closest_point(points, 3, greater_than=True)
    assert r2.outloc == 4


def test_modify_index_and_head_decompress(data, compressed_dfl_data):
    index = zran.Index.create_index(compressed_dfl_data, span=2**18)
    start = 0
    stop = 100

    compressed_range, uncompressed_range, new_index = index.create_modified_index([start], stop)
    length = start - uncompressed_range[0]
    offset = stop - start
    test_data = zran.decompress(
        compressed_dfl_data[compressed_range[0] : compressed_range[1]], new_index, length, offset
    )
    assert data[start:stop] == test_data


@pytest.mark.parametrize('start_index,stop_index', ((0, 5), (4, 10), (9, -1)))
def test_modify_index_and_interior_decompress(start_index, stop_index, data, compressed_dfl_data):
    index = zran.Index.create_index(compressed_dfl_data, span=2**18)
    start = index.points[start_index].outloc + 100
    stop = index.points[stop_index].outloc + 100

    compressed_range, uncompressed_range, new_index = index.create_modified_index([start], stop)
    length = start - uncompressed_range[0]
    offset = stop - start
    test_data = zran.decompress(
        compressed_dfl_data[compressed_range[0] : compressed_range[1]], new_index, length, offset
    )
    assert data[start:stop] == test_data


def test_modify_index_and_tail_decompress(data, compressed_dfl_data):
    index = zran.Index.create_index(compressed_dfl_data, span=2**18)
    start = index.points[-1].outloc + 100
    stop = len(data)

    compressed_range, uncompressed_range, new_index = index.create_modified_index([start], stop)
    length = start - uncompressed_range[0]
    offset = stop - start
    test_data = zran.decompress(
        compressed_dfl_data[compressed_range[0] : compressed_range[1]], new_index, length, offset
    )
    assert data[start:stop] == test_data


def test_index_after_end_decompress(data, compressed_dfl_data):
    index = zran.Index.create_index(compressed_dfl_data, span=2**18)
    with pytest.raises(ValueError, match='Offset and length specified would result in reading past the file bounds'):
        zran.decompress(compressed_dfl_data, index, 0, len(data) + 1)


def test_modified_after_end_decompress(data, compressed_dfl_data):
    index = zran.Index.create_index(compressed_dfl_data, span=2**18)
    start = index.points[5].outloc
    stop = index.points[10].outloc

    compressed_range, uncompressed_range, new_index = index.create_modified_index([start], stop)
    with pytest.raises(ValueError, match='Offset and length specified would result in reading past the file bounds'):
        zran.decompress(
            compressed_dfl_data[compressed_range[0] : compressed_range[1]],
            new_index,
            new_index.points[0].outloc + 10,
            new_index.uncompressed_size,
        )


def test_modified_nonzero_first_bits(data, compressed_dfl_data):
    index = zran.Index.create_index(compressed_dfl_data, span=2**16)

    nonfirst_zero_bit = False
    for point in index.points[1:]:
        if point.bits == 0:
            nonfirst_zero_bit = True

    if not nonfirst_zero_bit:
        print('Not enough index points to test this')

    for point in index.points:
        start = point.outloc
        compressed_range, uncompressed_range, new_index = index.create_modified_index([start])
        length = uncompressed_range[1] - uncompressed_range[0]
        test_data = zran.decompress(
            compressed_dfl_data[compressed_range[0] : compressed_range[1]],
            new_index,
            0,
            length,
        )
        true_data = data[uncompressed_range[0] : uncompressed_range[1]]
        assert true_data == test_data


@pytest.mark.skip(reason='Integration test. Only run if testing Sentinel-1 SLC burst compatibility')
@pytest.mark.parametrize('burst', offset_list)
def test_burst_extraction(burst, input_data):
    swath, golden, index = input_data
    compressed_range, uncompressed_range, new_index = index.create_modified_index([burst.start], burst.stop)
    data_subset = swath[compressed_range[0] : compressed_range[1]]
    test_data = zran.decompress(data_subset, new_index, burst.start - uncompressed_range[0], burst.stop - burst.start)
    assert golden[burst.start : burst.stop] == test_data
