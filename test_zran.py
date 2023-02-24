import os
import tempfile
import zlib

import pytest

import zran


# TODO null byte in data terminates window
@pytest.mark.xfail()
def test_index():
    data = os.urandom(2**24)
    compressed = zlib.compress(data, wbits=15 + zlib.MAX_WBITS)
    compressed_file = tempfile.NamedTemporaryFile()
    with open(compressed_file.name, 'wb') as f:
        f.write(compressed)

    index = zran.build_deflate_index(compressed_file.name)

    assert len(index[3]['window']) == 32768


def test_extract():
    start = 100
    length = 1000
    data = os.urandom(2**24)
    compressed = zlib.compress(data, wbits=15 + zlib.MAX_WBITS)
    compressed_file = tempfile.NamedTemporaryFile()
    with open(compressed_file.name, 'wb') as f:
        f.write(compressed)

    test_data = zran.extract_data(compressed_file.name, start, length)
    # TODO null byte in data terminates data
    print(len(test_data))
    assert data[start : start + len(test_data)] == test_data
