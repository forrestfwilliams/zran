import os
import tempfile
import zlib

import pytest

import zran

DFL_WBITS = -15
ZLIB_WBITS = 15
GZ_WBITS = 31


def write_compressed_file(uncompressed_data, filename, wbits, start=None, stop=None):
    compressed = zlib.compress(uncompressed_data, wbits=wbits)

    if not start:
        start = 0

    if not stop:
        stop = len(compressed)

    with open(filename, 'wb') as f:
        f.write(compressed[start:stop])


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
    name = 'tmp_no_head.gz'
    write_compressed_file(data, name, GZ_WBITS, start=987)
    yield name
    os.remove(name)


@pytest.fixture(scope='module')
def compressed_gz_file_no_tail(data):
    name = 'tmp_no_tail.gz'
    write_compressed_file(data, name, GZ_WBITS, stop=987)
    yield name
    os.remove(name)


@pytest.fixture(scope='module')
def compressed_gz_file(data):
    name = 'tmp.gz'
    write_compressed_file(data, name, GZ_WBITS)
    yield name
    os.remove(name)


@pytest.fixture(scope='module')
def compressed_dfl_file(data):
    name = 'tmp.dfl'
    write_compressed_file(data, name, DFL_WBITS)
    yield name
    os.remove(name)


@pytest.fixture(scope='module')
def compressed_zlib_file(data):
    name = 'tmp.zlib'
    write_compressed_file(data, name, ZLIB_WBITS)
    yield name
    os.remove(name)


@pytest.fixture(scope='function')
def compressed_file(request, compressed_gz_file, compressed_dfl_file, compressed_zlib_file):
    filenames = {'gz': compressed_gz_file, 'dfl': compressed_dfl_file, 'zlib': compressed_zlib_file}
    return filenames[request.param]


def test_build_deflate_index(compressed_gz_file):
    with open(compressed_gz_file, 'rb') as f:
        index = zran.build_deflate_index(f)

    points = index.points
    assert points[0].outloc == 0
    assert points[0].inloc == 10
    assert points[0].bits == 0
    assert len(points[0].window) == 32768


def test_build_deflate_index_fail(data, compressed_gz_file_no_head, compressed_gz_file_no_tail):
    with pytest.raises(zran.ZranError, match='zran: compressed data error in input file'):
        with open(compressed_gz_file_no_head, 'rb') as f:
            zran.build_deflate_index(f)

    with pytest.raises(zran.ZranError, match='zran: input file ended prematurely'):
        with open(compressed_gz_file_no_tail, 'rb') as f:
            zran.build_deflate_index(f)


@pytest.mark.parametrize('compressed_file', ['gz', 'dfl', 'zlib'], indirect=True)
def test_index_to_file(compressed_file):
    with open(compressed_file, 'rb') as f:
        index = zran.build_deflate_index(f)

    index.to_file('out.dflidx')
    with open('out.dflidx', 'rb') as f:
        dflidx = f.read()
    mode, length, have, points = zran.WrapperDeflateIndex.parse_dflidx(dflidx)
    assert dflidx[0:6] == b'DFLIDX'


def test_create_index_from_file(compressed_gz_file):
    index_file = tempfile.NamedTemporaryFile()
    with open(compressed_gz_file, 'rb') as f:
        index = zran.build_deflate_index(f)
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
    with open(compressed_file, 'rb') as f:
        test_data = zran.extract_data_with_tmp_index(f, start, length)
    assert data[start : start + length] == test_data


@pytest.mark.parametrize('compressed_file', ['gz', 'dfl', 'zlib'], indirect=True)
def test_extract_using_index(data, compressed_file):
    start = 100
    length = 1000
    with open(compressed_file, 'rb') as f:
        index = zran.build_deflate_index(f)
    index_file = tempfile.NamedTemporaryFile()
    index.to_file(index_file.name)
    del index

    with open(compressed_file, 'rb') as f:
        test_data = zran.extract_data(f, index_file.name, start, length)
    assert data[start : start + length] == test_data


def test_extract_using_index_fail(data, compressed_gz_file, compressed_gz_file_no_head):
    with open(compressed_gz_file, 'rb') as f:
        index = zran.build_deflate_index(f)

    index_file = tempfile.NamedTemporaryFile()
    index.to_file(index_file.name)
    del index

    start = 100
    length = 1000
    with pytest.raises(zran.ZranError, match='zran: compressed data error in input file'):
        with open(compressed_gz_file_no_head, 'rb') as f:
            zran.extract_data(f, index_file.name, start, length)


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
