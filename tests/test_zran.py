import os
import tempfile
import zlib
from collections import namedtuple

import pytest

import zran

DFL_WBITS = -15
ZLIB_WBITS = 15
GZ_WBITS = 31

Offset = namedtuple('Offset', ['start', 'stop'])
offset_list = [
    Offset(start=109395, stop=149033895),
    Offset(start=149033895, stop=297958395),
    Offset(start=297958395, stop=446882895),
    Offset(start=446882895, stop=595807395),
    Offset(start=595807395, stop=744731895),
    Offset(start=744731895, stop=893656395),
    Offset(start=893656395, stop=1042580895),
    Offset(start=1042580895, stop=1191505395),
    Offset(start=1191505395, stop=1340429895),
]


@pytest.fixture(scope='module')
def input_data():
    slc_name = 'tests/S1A_IW_SLC__1SDV_20200604T022251_20200604T022318_032861_03CE65_7C85.zip'
    iw3_vv_start, iw3_vv_stop = (35813, 862111605)
    if not os.path.isfile(slc_name):
        raise FileNotFoundError(f'{slc_name} must be present')

    with open(slc_name, 'rb') as f:
        f.seek(iw3_vv_start)
        body = f.read(iw3_vv_stop - iw3_vv_start)
    index = zran.Index.create_index(body, span=2**20)
    golden = zlib.decompress(body, wbits=DFL_WBITS)

    yield (body, golden, index)

    del body
    del golden
    del index


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


@pytest.mark.parametrize('start_index,stop_index', ((0, 5), (4, 10), (9, -1)))
def test_modify_index_and_decompress(start_index, stop_index, data, compressed_dfl_data):
    index = zran.Index.create_index(compressed_dfl_data, span=2**18)
    start = index.points[start_index].outloc + 100
    stop = index.points[stop_index].outloc + 100

    compressed_range, uncompressed_range, new_index = index.create_modified_index([start], [stop])
    test_data = zran.decompress(
        compressed_dfl_data[compressed_range[0] : compressed_range[1]],
        new_index,
        start - uncompressed_range[0],
        stop - start,
    )
    assert data[start:stop] == test_data


@pytest.mark.skip('Integration test. Only run if testing Sentinel-1 SLC burst compatibility')
@pytest.mark.parametrize('burst', offset_list)
def test_safe(burst, input_data):
    swath, golden, index = input_data
    compressed_range, uncompressed_range, new_index = index.create_modified_index([burst.start], [burst.stop])
    data_subset = swath[compressed_range[0] : compressed_range[1]]
    test_data = zran.decompress(data_subset, new_index, burst.start - uncompressed_range[0], burst.stop - burst.start)
    assert golden[burst.start : burst.stop] == test_data
