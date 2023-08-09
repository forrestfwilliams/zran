import os
import random
import zlib

import pytest

import zran

DFL_WBITS = -15
ZLIB_WBITS = 15
GZ_WBITS = 31


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
    compress_obj = zlib.compressobj(wbits=wbits, level=9)
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
    # Can't use os.random directly because there needs to be some
    # repitition in order for compression to be effective
    words = [os.urandom(8) for _ in range(1000)]
    out = b''.join([random.choice(words) for _ in range(524288)])
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
