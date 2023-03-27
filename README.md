# ZRAN

## Random read access for ZLIB, GZIP and DEFLATE file formats

## Description
`zran` is a Python extension that wraps the [zran](https://github.com/madler/zlib/blob/master/examples/zran.h) library, which was created by Mark Adler (the creator of `zlib`). This utility will create an index that will allow you to begin decompressing DEFLATE-compressed data (ZLIB, GZIP, or DEFLATE format) from compression block boundaries on subsequent reads. This effectively allows you to randomly access DEFLATE-compressed data once the index is created.

## Installation
`zran` can be installed in your preferred Python environment via pip:

```bash
python -m pip install zran
```

Currently, only macOS/Linux x86_64 and ARM64 architectures are supported. Please open an issue or submit a PR if you would like to see support for other platforms!

## Usage
To use `zran`, you need to:

1. Create an index for a compressed file
2. Save this index
3. Use this index to access the data on subsequent reads

To create and save the index:
```python
import zran

with open('compressed.gz', 'rb') as f:
    compressed_file = f.read()
    index = zran.Index.create_index(compressed_file)
```
This `Index` can be written to a file (`index.to_file('index.dflidx')`), or directly passed to `zran.deompress`:
```python
start = 1000
length = 2000
data = zran.decompress(compressed_file, index, start, length)
```

That's it!

## Contributing
We use the standard GitHub flow to manage contributions to this project. Check out this [documentation](https://docs.github.com/en/get-started/quickstart/github-flow) if you are unfamiliar with this process.

You can install a development version of `zran` via pip as well:
```bash
git clone https://github.com/forrestfwilliams/zran.git
cd zran
python -m pip install .
```
Then, run `pytest` to ensure that all tests are passing. We use [black](https://black.readthedocs.io/en/stable/) with `line-length 120` for formatting and [ruff](https://beta.ruff.rs/docs/) for linting. Please ensure that your code is correctly formatted and linted before submitting a PR. As far as I can tell, pip installing with the `--editable` command is not valid when the code needs to be compiled, so you will need to re-install the package if you make any changes.

## Similar Projects
If you prefer to work in the C programming language, you may want to work directly with the `zran` source C code in the [zlib](https://github.com/madler/zlib) library. Paul McCarthy's [`indexed_gzip`](https://github.com/pauldmccarthy/indexed_gzip) library was a huge inspiration for this project, and in particular was a huge help while creating our `setup.py` file. If you plan to work exclusively with gzip files, you may be better served by the `indexed_gzip` library. However, this project has some unique functionality that sets it apart:

* Use of the most up-to-date version of the `zran` C library
* Support for ZLIB, GZIP, and DEFLATE formatted data
* Greater visibility into the contents of indexes
* Compression of the indexes when written to a file, leading to smaller index file sizes
* The ability to modify the points contained within an index via the `Index.create_modified_index()` method

