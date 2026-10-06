"""Load the game executable from whatever file the user has."""

from pathlib import Path

from ..equipment import CodeBinError, verify_code
from .extract import ExtractError, extract_code

CONTAINER_MAGICS = (b"NCSD", b"NCCH")


def is_container(path: Path) -> bool:
    """True for a .3ds/.cci (NCSD) or .app/.cxi (NCCH), as opposed to a loose game file."""
    with Path(path).open("rb") as f:
        header = f.read(0x104)
    return header[0x100:0x104] in CONTAINER_MAGICS


def load_code(path: Path) -> bytes:
    """Decompressed, verified code.bin from a code.bin, a decrypted .3ds or an update's .app."""
    path = Path(path)
    if is_container(path):
        try:
            code, _ = extract_code(path)
        except ExtractError as error:
            raise CodeBinError(str(error)) from error
    else:
        code = path.read_bytes()
    verify_code(code)
    return code
