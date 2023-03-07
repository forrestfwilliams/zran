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
def compressed_gz_file_no_head(data):
    compressed_data = create_compressed_data(data, GZ_WBITS, start=1562)
    yield compressed_data
    del compressed_data


@pytest.fixture(scope='module')
def compressed_gz_file_no_tail(data):
    compressed_data = create_compressed_data(data, GZ_WBITS, stop=-1587)
    yield compressed_data
    del compressed_data


@pytest.fixture(scope='module')
def compressed_gz_file(data):
    compressed_data = create_compressed_data(data, GZ_WBITS)
    yield compressed_data
    del compressed_data


@pytest.fixture(scope='module')
def compressed_dfl_file(data):
    compressed_data = create_compressed_data(data, DFL_WBITS)
    yield compressed_data
    del compressed_data


@pytest.fixture(scope='module')
def compressed_zlib_file(data):
    compressed_data = create_compressed_data(data, ZLIB_WBITS)
    yield compressed_data
    del compressed_data


@pytest.fixture(scope='function')
def compressed_file(request, compressed_gz_file, compressed_dfl_file, compressed_zlib_file):
    filenames = {'gz': compressed_gz_file, 'dfl': compressed_dfl_file, 'zlib': compressed_zlib_file}
    return filenames[request.param]


def test_build_deflate_index(compressed_gz_file):
    index = zran.build_deflate_index(compressed_gz_file)

    points = index.points
    assert points[0].outloc == 0
    assert points[0].inloc == 10
    assert points[0].bits == 0
    assert len(points[0].window) == 32768


def test_build_deflate_index_fail(data, compressed_gz_file_no_head, compressed_gz_file_no_tail):
    with pytest.raises(zran.ZranError, match='zran: compressed data error in input file'):
        zran.build_deflate_index(compressed_gz_file_no_head)

    with pytest.raises(zran.ZranError, match='zran: input file ended prematurely'):
        zran.build_deflate_index(compressed_gz_file_no_tail)


@pytest.mark.parametrize('compressed_file', ['gz', 'dfl', 'zlib'], indirect=True)
def test_index_to_file(compressed_file):
    index = zran.build_deflate_index(compressed_file)

    index.to_file('out.dflidx')
    with open('out.dflidx', 'rb') as f:
        dflidx = f.read()
    mode, length, have, points = zran.WrapperDeflateIndex.parse_dflidx(dflidx)
    assert dflidx[0:6] == b'DFLIDX'


def test_create_index_from_file(compressed_gz_file):
    index_file = tempfile.NamedTemporaryFile()
    index = zran.build_deflate_index(compressed_gz_file)
    index.to_file(index_file.name)
    del index

    new_index = zran.WrapperDeflateIndex.from_file(index_file.name)

    assert new_index.mode == 31
    assert new_index.points[0].outloc == 0
    assert new_index.points[0].inloc == 10
    assert new_index.points[0].bits == 0
    assert len(new_index.points[0].window) == 32768


@pytest.mark.parametrize('compressed_file', ['gz', 'dfl', 'zlib'], indirect=True)
def test_extract_data_with_tmp_index(data, compressed_file):
    start = 100
    length = 1000
    test_data = zran.extract_data_with_tmp_index(compressed_file, start, length)
    assert data[start : start + length] == test_data


@pytest.mark.parametrize('compressed_file', ['gz', 'dfl', 'zlib'], indirect=True)
def test_extract_using_index(data, compressed_file):
    start = 100
    length = 1000

    index = zran.build_deflate_index(compressed_file)
    index_file = tempfile.NamedTemporaryFile()
    index.to_file(index_file.name)
    del index

    test_data = zran.extract_data(compressed_file, index_file.name, start, length)
    assert data[start : start + length] == test_data


def test_extract_using_index_fail(data, compressed_gz_file, compressed_gz_file_no_head):
    index = zran.build_deflate_index(compressed_gz_file)

    index_file = tempfile.NamedTemporaryFile()
    index.to_file(index_file.name)
    del index

    start = 100
    length = 1000
    with pytest.raises(zran.ZranError, match='zran: compressed data error in input file'):
        zran.extract_data(compressed_gz_file_no_head, index_file.name, start, length)


def test_get_closest_point():
    points = [zran.Point(0, 0, 0, b''), zran.Point(2, 0, 0, b''), zran.Point(4, 0, 0, b''), zran.Point(5, 0, 0, b'')]
    r1 = zran.get_closest_point(points, 3)
    assert r1.outloc == 2

    r2 = zran.get_closest_point(points, 3, greater_than=True)
    assert r2.outloc == 4


def test_modify_points(gz_points):
    result = zran.modify_points(gz_points, offset=1000)
    assert result[0].outloc == 0
    assert result[3].outloc == 400
