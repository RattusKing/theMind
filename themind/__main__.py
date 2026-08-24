"""theMind command line — carry a mind around without writing Python.

    python3 -m themind export ./my-mind             # one file, the whole mind
    python3 -m themind export ./my-mind -o back.json
    python3 -m themind restore back.json ./new-home

Export writes the single-file snapshot FORMAT.md describes; restore recreates
a mind folder from one. Both are the same `Mind.export` / `Mind.restore` the
library exposes — this is just the door for people using the proxy, who never
touch code.
"""
import argparse
import os
import sys

from .mind import Mind


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="python3 -m themind",
        description="theMind: export a mind to one file, or restore one from it.")
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("export", help="write a single-file snapshot of a mind")
    e.add_argument("mind", help="the mind's folder")
    e.add_argument("-o", "--out", default=None,
                   help="where to write it (default: <mind>/mind-export.json)")

    r = sub.add_parser("restore", help="recreate a mind folder from an export file")
    r.add_argument("export_file", help="a file written by export")
    r.add_argument("dest", help="the folder to become the mind (created if missing)")

    args = p.parse_args(argv)
    if args.cmd == "export":
        # Refuse to invent a mind out of a typo: export reads, it never creates.
        if not os.path.isfile(os.path.join(args.mind, "manifest.json")):
            print("not a mind folder (no manifest.json): %s" % args.mind, file=sys.stderr)
            return 2
        print(Mind(args.mind).export(args.out))
        return 0
    try:
        Mind.restore(args.export_file, args.dest)
    except FileNotFoundError:
        print("no such export file: %s" % args.export_file, file=sys.stderr)
        return 2
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    print(args.dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
