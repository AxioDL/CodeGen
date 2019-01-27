import sys
import argparse
from typing import List

from codegen import codegen


class ArgumentData(object):
    def __init__(self) -> None:
        self.command = ''
        self.source_file = ''
        self.libclangpath = ''
        self.include_paths: List[str] = []
        self.source_root = ''
        self.output_root = ''
        self.cache_path = None


argparser = argparse.ArgumentParser()
argparser.add_argument('command', help='What to do')
argparser.add_argument('source_file', help='Source file to use')
argparser.add_argument('--libclangpath', help='Path to libclang library file', required=True)
argparser.add_argument('--include', '-I', help='Define an include path', dest='include_paths', action='append')
argparser.add_argument('--source-root', help='Root path of all source files', required=True)
argparser.add_argument('--output-root', help='Root path of all files to be output', required=True)
argparser.add_argument('--cache-path', help='Path to a directory to store output file caches in')


def main() -> int:
    args = ArgumentData()

    # noinspection PyTypeChecker
    argparser.parse_args(namespace=args)

    if args.command.lower() == 'get_output_files':
        return do_get_output_files_command(args)
    if args.command.lower() == 'generate':
        return do_generate_command(args)

    sys.stderr.write('Invalid Command\n')
    return 1


def do_get_output_files_command(args: ArgumentData) -> int:
    output_files = codegen.get_output_files(
        args.source_file,
        args.include_paths,
        args.libclangpath,
        args.source_root,
        args.output_root,
        args.cache_path
    )
    sys.stdout.write(';'.join(output_files))
    return 0


def do_generate_command(args: ArgumentData) -> int:
    codegen.RunCodegen(args.source_file, args.include_paths, args.libclangpath, args.source_root, args.output_root)
    return 0
