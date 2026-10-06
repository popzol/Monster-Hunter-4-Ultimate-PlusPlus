"""Extract the decompressed executable from a decrypted .3ds or update .app.

    python tools/extract_code_bin.py FILE [--out Documentation/exefs/code.bin]

For an installed update use its content 00000000.app (Citra: right click the
game > Open Update Data Location).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mh4u_rando.exefs.extract import extract_code  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--out", type=Path, default=Path("Documentation/exefs/code.bin"))
    args = parser.parse_args()
    code, title_id = extract_code(args.file)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(code)
    print(f"{args.out}: {len(code):,} bytes (title {title_id})")


if __name__ == "__main__":
    main()
