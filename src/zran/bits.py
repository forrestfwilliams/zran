import os
import random
import zlib

import zran

DFL_WBITS = -15

words = [os.urandom(8) for _ in range(1000)]
uncompressed_data = b''.join([random.choice(words) for _ in range(524288)])

compress_obj = zlib.compressobj(wbits=DFL_WBITS, level=6)
compressed_data = compress_obj.compress(uncompressed_data)
compressed_data += compress_obj.flush()

index = zran.Index.create_index(compressed_data, span=2**17)

zero_bit_loc = []
nonzero_bit_loc = []
for i, point in enumerate(index.points):
    if point.bits == 0:
        zero_bit_loc.append(i)
    else:
        nonzero_bit_loc.append(i)

def test_an_index(point_index, index, uncompressed_data):
    start = index.points[point_index].outloc
    stop = len(uncompressed_data)
    compressed_range, uncompressed_range, new_index = index.create_modified_index([start], [stop], False)
    length = stop - start
    test_data = zran.decompress(compressed_data[index.points[point_index].inloc:], new_index, 0, length)
    true_data = uncompressed_data[start:stop]
    if true_data == test_data:
        print('Success')
    else:
        print('No error, but decompressed data incorrect')

try:
    test_an_index(zero_bit_loc[1], index, uncompressed_data)
except zran.ZranError as e:
    print(f'Failure with message: {e}')

try:
    test_an_index(nonzero_bit_loc[1], index, uncompressed_data)
except zran.ZranError as e:
    print(f'Failure with message: {e}')
