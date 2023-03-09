import os
import tempfile
import zlib

import pytest

import zran

DFL_WBITS = -15
ZLIB_WBITS = 15
GZ_WBITS = 31


def create_compressed_data(uncompressed_data, wbits, start=None, stop=None):
    compress_obj = zlib.compressobj(wbits=wbits)
    compressed = compress_obj.compress(uncompressed_data)
    compressed += compress_obj.flush()

    if not start:
        start = 0

    if not stop:
        stop = len(compressed)

    return compressed[start:stop]


@pytest.fixture(scope='module')
def gz_points():
    values = [
        zran.Point(0, 1010, 0, b''),
        zran.Point(200, 1110, 0, b''),
        zran.Point(300, 1210, 0, b''),
        zran.Point(400, 1310, 0, b''),
    ]
    return values


@pytest.fixture(scope='module')
def data():
    out = os.urandom(2**22)
    return out


@pytest.fixture(scope='module')
def compressed_gz_data_no_head(data):
    compressed_data = create_compressed_data(data, GZ_WBITS, start=1562)
    yield compressed_data
    del compressed_data


@pytest.fixture(scope='module')
def compressed_gz_data_no_tail(data):
    compressed_data = create_compressed_data(data, GZ_WBITS, stop=-1587)
    yield compressed_data
    del compressed_data


@pytest.fixture(scope='module')
def compressed_gz_data(data):
    compressed_data = create_compressed_data(data, GZ_WBITS)
    yield compressed_data
    del compressed_data


@pytest.fixture(scope='module')
def compressed_dfl_data(data):
    compressed_data = create_compressed_data(data, DFL_WBITS)
    yield compressed_data
    del compressed_data


@pytest.fixture(scope='module')
def compressed_zlib_data(data):
    compressed_data = create_compressed_data(data, ZLIB_WBITS)
    yield compressed_data
    del compressed_data


@pytest.fixture(scope='function')
def compressed_file(request, compressed_gz_data, compressed_dfl_data, compressed_zlib_data):
    filenames = {'gz': compressed_gz_data, 'dfl': compressed_dfl_data, 'zlib': compressed_zlib_data}
    return filenames[request.param]


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


def test_create_index_fail_head(data, compressed_gz_data_no_head):
    with pytest.raises(zran.ZranError, match='zran: compressed data error in input file'):
        zran.Index.create_index(compressed_gz_data_no_head)


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


@pytest.mark.skip
@pytest.mark.parametrize('start_index,stop_index', ((0, 5), (4, 10), (9, -1)))
def test_modify_index_and_decompress(start_index, stop_index, data, compressed_dfl_data):
    index = zran.build_deflate_index(compressed_dfl_data, span=2**18)
    start = index.points[start_index].outloc + 100
    stop = index.points[stop_index].outloc + 100

    inloc_range, outloc_range, desired_points = zran.modify_points(
        index.points, len(compressed_dfl_data), index.length, [start], [stop]
    )
    new_length = desired_points[-1].outloc - desired_points[0].outloc
    dflidx = zran.create_index_file(index.mode, new_length, len(desired_points), desired_points)

    index_file = tempfile.NamedTemporaryFile()
    with open(index_file.name, "wb") as f:
        f.write(dflidx)
    del index

    test_data = zran.decompress(
        compressed_dfl_data[inloc_range[0] : inloc_range[1]], index_file.name, start - outloc_range[0], stop - start
    )
    assert data[start:stop] == test_data
