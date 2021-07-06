#!/usr/bin/env python

__author__ = 'SutandoTsukai181'
__version__ = '1.0'

import gzip
import os
import shutil
from argparse import ArgumentParser

from binary_reader import *

ENCODING = 'cp932'


def remove_path(path, force_overwrite: bool) -> bool:
    if (not force_overwrite) and input('Output path exists. Overwrite? (Y/N) ').lower() != 'y':
        print('User cancelled.')
        return False

    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
    except:
        print('Error: Could not remove existing path.')
        return False

    return True


def write_gzip_name(name: str, data: bytes) -> bytearray:
    br = BinaryReader(data)

    # Enable FNAME flag
    br.seek(3)
    flags = br.read_uint8()
    br.seek(3)
    br.write_uint8(flags | 8)

    # Set operating system flag to Unix
    br.seek(9)
    br.write_uint8(3)

    # Write the file name
    buf = br.buffer()[br.pos():]
    br.write_str(name, True)

    return br.buffer()[:br.pos()] + buf


def unpack(in_path: str, out_path: str, force_overwrite: bool) -> None:
    if os.path.exists(out_path):
        # Clear the existing output directory
        if not remove_path(out_path, force_overwrite):
            print('Aborting.')
            return

        print()

    # Create an empty directory
    os.mkdir(out_path)

    with open(in_path, 'rb') as f:
        farc = BinaryReader(f.read(), Endian.BIG, ENCODING)

    # FArc is uncompressed, FArC uses gzip compression
    magic = farc.read_str(4)
    if magic not in ['FArc', 'FArC']:
        print(f'Error: unexpected magic: {magic}')
        return

    is_compressed = magic == 'FArC'

    header_size = farc.read_uint32() + 8
    farc.read_uint32()  # Alignment size for header and data buffer

    entries = list()
    while farc.pos() < header_size:
        # File name, offset, size
        entries.append((farc.read_str(), *farc.read_uint32(2)))

        if is_compressed:
            # Size decompressed
            farc.read_uint32()

    buffer = farc.buffer()
    for (name, offset, size) in entries:
        data = buffer[offset: offset + size]

        if is_compressed:
            data = gzip.decompress(data)

        print(f'Writing {name} ...')
        with open(os.path.join(out_path, name), 'wb') as f:
            f.write(data)

    print(f'\nFArc was unpacked to "{out_path}"')


def repack(in_path: str, out_path: str, force_overwrite: bool, use_compression: bool, align_value: int) -> None:
    if os.path.exists(out_path):
        # Clear the existing output file
        if not remove_path(out_path, force_overwrite):
            print('Aborting.')
            return

        print()

    file_paths = list()
    for root, _, files in os.walk(in_path):
        for f in files:
            file_paths.append((f, os.path.join(root, f)))

        # Only get the files in the root of the input path
        break

    # Entry size without string
    entry_size = 0xC if use_compression else 8

    # Header size from the start of the file
    org_header_size = header_size = sum(map(lambda x: len(x[0].encode(ENCODING)) + 1 + entry_size, file_paths)) + 0xC

    if header_size % align_value:
        header_size += align_value - (header_size % align_value)

    farc = BinaryReader(endianness=Endian.BIG)
    farc.write_str('FArC' if use_compression else 'FArc')
    farc.write_uint32(org_header_size - 8)
    farc.write_uint32(align_value)

    data_br = BinaryReader()
    for name, path in file_paths:
        print(f'Adding {name} ...')
        farc.write_str(name, True)

        # Offset
        farc.write_uint32(header_size + data_br.size())

        with open(path, 'rb') as f:
            data = f.read()

        if use_compression:
            # Compress the file and add its name to the header (since gzip.compress does not do that)
            compressed_data = write_gzip_name(name, gzip.compress(data))
            farc.write_uint32(len(compressed_data))  # Size of compressed file

            data_br.extend(compressed_data)
        else:
            data_br.extend(data)

        # Align data after adding the file
        data_br.align(align_value)

        # Size of decompressed file
        farc.write_uint32(len(data))

    # Align after header
    farc.align(align_value)

    farc.extend(data_br.buffer())
    farc.seek(data_br.size(), Whence.CUR)

    # Write output file
    with open(out_path, 'wb') as f:
        f.write(farc.buffer())

    print(f'\nFolder was repacked to "{out_path}"')


def main():
    print(f'PyFArc v{__version__}')
    print(f'By {__author__}\n')

    parser = ArgumentParser(
        description='Unpacks/repacks Virtua Fighter 5 FArc archives',
        epilog='If PATH is a FArc file, it will be extracted to a folder with the same name.'
        ' If PATH is a folder, all of the files in its root will be packed to a new FArc file with the same name.'
    )

    parser.add_argument('path', metavar='PATH', action='store',
                        help='path to .farc file or folder to repack')
    parser.add_argument('-f', '--force-overwrite', action='store_true', dest='force_overwrite',
                        help='force overwrite files without showing a prompt')
    parser.add_argument('-c', '--compress', action='store_true',
                        help='use compression when repacking')
    parser.add_argument('-a', '--align', action='store', type=int, default=1,
                        help='set alignment value for header and data when repacking (defaults to 1)')

    args = parser.parse_args()

    if not os.path.exists(args.path):
        print('Error: path does not exist.')
        os.system('pause')
        return

    if os.path.isfile(args.path):
        print('Unpacking FArc file...\n')
        unpack(args.path, args.path[:args.path.rfind('.')] if '.' in args.path else f'{args.path}_unpacked', args.force_overwrite)
    elif os.path.isdir(args.path):
        print('Repacking folder to FArc...\n')
        repack(args.path, f'{args.path}.farc', args.force_overwrite, args.compress, max(1, args.align))
    else:
        print('Error: path is invalid.')
        os.system('pause')
        return

    print('\nProgram finished.')
    os.system('pause')


if __name__ == '__main__':
    main()
