# ZRAN

## Random read access for gzip and zip files

## Description
`zran` is a Python extension that wraps the [zran](https://github.com/madler/zlib/blob/master/examples/zran.h) library, which was created by Mark Adler (the creator of `zlib`). This utility allows you to create an index that allows you begin decompressing DEFLATE-compressed data (ZLIB, GZIP, or DEFLATE format) from compression block boundaries. This effectively allows you to randomly access DEFLATE-compressed data once the index is created.

## Installation
In your preferred python environment:
```bash
git clone https://github.com/forrestfwilliams/zran.git
cd zran
python -m pip install .
```
As far as I can tell, pip installing with the `--editable` command is not valid when the code needs to be compiled, so you will need to re-install the package if you make any changes.

## Usage
To use `zran`, you need to:

1. Create an index for a compressed file
2. Save this index
3. Use this index to access the data on subsequent reads

To create and save the index:
```python
import zran

with open('compressed.gz', 'rb') as f:
    index = zran.create_deflate_index(f)

index.to_file('index.dflidx')
```

Then, to use the index and read data:
```python
with open('compressed.gz', 'rb') as f:
    data = zran.extract_data(f, 'index.dflidx', offset=100, length=1000)
```

That's it!
