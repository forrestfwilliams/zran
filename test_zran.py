import os
import tempfile
import zlib

import pytest

import zran


@pytest.fixture
def gz_points():
    values = [
        zran.Point(0, 1010, 0, b''),
        zran.Point(200, 1110, 0, b''),
        zran.Point(300, 1210, 0, b''),
        zran.Point(400, 1310, 0, b''),
    ]
    return values


def test_index():
    data = os.urandom(2**24)
    compressed = zlib.compress(data, wbits=15 + zlib.MAX_WBITS)
    compressed_file = tempfile.NamedTemporaryFile()
    with open(compressed_file.name, 'wb') as f:
        f.write(compressed)

    # index = zran.build_deflate_index(compressed_file.name)
    with open(compressed_file.name, 'rb') as f:
        index = zran.build_deflate_index(f)

    points = index.points
    assert points[0].outloc == 0
    assert points[0].inloc == 10
    assert points[0].bits == 0
    assert len(points[0].window) == 32768


def test_build_deflate_index_fail():
    data = os.urandom(2**24)
    compressed = zlib.compress(data, wbits=15 + zlib.MAX_WBITS)

    # Check missing head
    missing_head = tempfile.NamedTemporaryFile()
    with open(missing_head.name, 'wb') as f:
        # Corrupt data on purpose
        f.write(compressed[100:])

    with pytest.raises(zran.ZranError, match='zran: compressed data error in input file'):
        with open(missing_head.name, 'rb') as f:
            zran.build_deflate_index(f)

    # Check missing tail
    missing_tail = tempfile.NamedTemporaryFile()
    with open(missing_tail.name, 'wb') as f:
        # Corrupt data on purpose
        f.write(compressed[:-10])

    with pytest.raises(zran.ZranError, match='zran: input file ended prematurely'):
        with open(missing_tail.name, 'rb') as f:
            zran.build_deflate_index(f)


def test_index_to_file():
    data = os.urandom(2**24)
    compressed = zlib.compress(data, wbits=15 + zlib.MAX_WBITS)
    compressed_file = tempfile.NamedTemporaryFile()
    with open(compressed_file.name, 'wb') as f:
        f.write(compressed)

    with open(compressed_file.name, 'rb') as f:
        index = zran.build_deflate_index(f)

    index.to_file('out.dflidx')
    with open('out.dflidx', 'rb') as f:
        dflidx = f.read()
    mode, length, have, points = zran.WrapperDeflateIndex.parse_dflidx(dflidx)
    assert dflidx[0:6] == b'DFLIDX'


def test_create_index_from_file():
    data = os.urandom(2**24)
    compressed = zlib.compress(data, wbits=15 + zlib.MAX_WBITS)
    compressed_file = tempfile.NamedTemporaryFile()
    with open(compressed_file.name, 'wb') as f:
        f.write(compressed)

    index_file = tempfile.NamedTemporaryFile()
    with open(compressed_file.name, 'rb') as f:
        index = zran.build_deflate_index(f)
    index.to_file(index_file.name)
    del index

    new_index = zran.WrapperDeflateIndex.from_file(index_file.name)
    assert new_index.points[0].outloc == 0


def test_extract_data_with_tmp_index():
    start = 100
    length = 1000
    data = os.urandom(2**24)
    compressed = zlib.compress(data, wbits=15 + zlib.MAX_WBITS)
    compressed_file = tempfile.NamedTemporaryFile()
    with open(compressed_file.name, 'wb') as f:
        f.write(compressed)

    with open(compressed_file.name, 'rb') as f:
        test_data = zran.extract_data_with_tmp_index(f, start, length)
    assert data[start : start + length] == test_data


def test_extract_using_index():
    start = 100
    length = 1000

    data = os.urandom(2**24)
    compressed = zlib.compress(data, wbits=15 + zlib.MAX_WBITS)
    compressed_file = tempfile.NamedTemporaryFile()
    with open(compressed_file.name, 'wb') as f:
        f.write(compressed)

    with open(compressed_file.name, 'rb') as f:
        index = zran.build_deflate_index(f)

    index_file = tempfile.NamedTemporaryFile()
    index.to_file(index_file.name)
    del index

    with open(compressed_file.name, 'rb') as f:
        test_data = zran.extract_data(f, index_file.name, start, length)
    assert data[start : start + length] == test_data


def test_extract_using_index_fail():
    start = 100
    length = 1000

    data = os.urandom(2**24)
    compressed = zlib.compress(data, wbits=15 + zlib.MAX_WBITS)
    compressed_file = tempfile.NamedTemporaryFile()
    with open(compressed_file.name, 'wb') as f:
        f.write(compressed)

    compressed_file_bad = tempfile.NamedTemporaryFile()
    with open(compressed_file_bad.name, 'wb') as f:
        f.write(compressed[1000:])

    with open(compressed_file.name, 'rb') as f:
        index = zran.build_deflate_index(f)

    index_file = tempfile.NamedTemporaryFile()
    index.to_file(index_file.name)
    del index

    with pytest.raises(zran.ZranError, match='zran: compressed data error in input file'):
        with open(compressed_file_bad.name, 'rb') as f:
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
