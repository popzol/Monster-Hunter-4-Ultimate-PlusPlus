"""Build a music test mod for Citra (see docs/music.md).

    python tools/music_probe.py --out DIR [--probes LETTERS] [--base MOD_DIR] [--rom GAME.3ds]

Writes DIR/romfs/... and DIR/LEEME.txt; copy romfs into load/mods/0004000000126100/. The game reads the queues
(.stq) from ARCs, so every queue change is written into them (core_title / core_quest / core_event per language,
loc/data/mNN.arc); `--base` is a mod folder whose ARCs are patched instead of the game's (keeps its HUD and icons).
`--probes` picks which checks to include (default TBCDE); each is independent and writes its own files:

  T. The title screen's theme is replaced by the synthetic seam test of tools/music_replace.py (our encoder, a
     replaced .mca with its entry updated): heard at boot, it checks the whole chain and the loop seam.
  A. Tigrex's own stream entry (battle queue) is pointed at Gogmazios's track: a stream may play a .mca of
     another folder, like B but for a monster theme (bgm_bat, in core_quest/core_event: not in TBCDE by
     default since it alone was suspected of a quest-load hang, see docs/music.md).
  B. The Ancestral Steppe's field battle theme is replaced by a stream entry pointing at Ukanlos's
     theme in sound/bgm/battle: a stream may play a .mca of another folder (queue only).
  C. bgm_stage_02.mca (Sunken Hollow) is replaced by Seregios's theme and its stream entry is updated:
     a replaced retail .mca with a matching entry.
  D. bgm_stage_03.mca (Primal Forest) is replaced by the seam test but its queue is left as it was: whether
     the game needs the entry to match the file (the seam test played; once with Kushala's theme the original
     was heard).
  E. bgm_stage_05.mca (Heaven's Mount) is its own theme decoded and re-encoded by our encoder with the retail
     loop points: our encoder on real music (should sound like the original, loop at ~1:41 included).
  M. Tigrex's bgm_em011.mca is replaced by the seam test and its entry in the battle queue updated: a custom
     monster theme, the mechanism of T and C in bgm_bat.
"""

import argparse
import sys
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from music_replace import encode_track, mod_reader, open_game, replace_track, seam_test, write_files  # noqa: E402

from mh4u_rando.audio import (build_strq, decode_madp, parse_madp, parse_strq, queue_files,  # noqa: E402
                              read_queue, romfs_path, stream_entry)
from mh4u_rando.exefs import RomFS  # noqa: E402

TITLE_QUEUE = "sound\\bgm\\system\\bgm_sys"
TITLE = "sound\\bgm\\system\\wav\\bgm_title"
BATTLE = "sound\\bgm\\battle\\bgm_bat"
TIGREX_REQUEST = 0x0B
TIGREX = "sound\\bgm\\battle\\wav\\bgm_em011"
GOGMAZIOS = "sound\\bgm\\battle\\wav\\bgm_em089"
UKANLOS = "sound\\bgm\\battle\\wav\\bgm_em116"
SEREGIOS = "sound\\bgm\\battle\\wav\\bgm_em088"
KUSHALA = "sound\\bgm\\battle\\wav\\bgm_em031"
FIELD_STREAM = 1  # bgm_stage_NN in bgm_st_NN (request 0x0B)

README_HEADER = """Prueba de musica (tools/music_probe.py). Antes de copiar, BORRA la carpeta
romfs/sound de la prueba anterior en load/mods/0004000000126100/ (sus .stq sueltos
no los lee el juego y sus .mca confundirian las pruebas). Luego copia la carpeta
romfs de aqui en load/mods/0004000000126100/, cierra Citra del todo y vuelve a
abrirlo (los mods se leen al arrancar el juego) y comprueba:

"""
README_LETTERS = {
    "T": """T. Pantalla de titulo, nada mas arrancar: en vez de la musica del titulo suenan
   4 notas que suben y despues un acorde con un metronomo; el primer golpe de
   cada vuelta (cada 8 s) es mas agudo. El ritmo no debe tropezar ni hacer clic.
   Si aqui suena la musica normal, para y dimelo: lo demas tampoco funcionara.
""",
    "A": """A. Cualquier mision con Tigrex (fuera de la Arena / Cima de la Torre): al pelear
   debe sonar el tema de Gogmazios en vez del de Tigrex. Si la mision no llega a
   cargar, dimelo: antes paso con un mecanismo distinto para este mismo cambio.
""",
    "B": """B. Estepa Ancestral, peleando con un monstruo SIN tema propio (Rathian,
   Kecha Wacha, Rathalos...): debe sonar el tema de Ukanlos (y hacer loop).
""",
    "C": """C. Hondonada Sumergida, monstruo sin tema propio: debe sonar el tema de
   Seregios entero y hacer loop sin cortes.
""",
    "D": """D. Bosque Primigenio, monstruo sin tema propio: el .mca es la prueba sintetica
   del titulo (4 notas, acorde y metronomo) pero la cola conserva la entrada del
   tema original. Apunta si suena la prueba, el tema de siempre, silencio o se
   cuelga.
""",
    "M": """M. Cualquier mision con Tigrex (fuera de la Arena / Cima de la Torre): al pelear
   debe sonar la prueba sintetica del titulo (4 notas, acorde y metronomo) en
   vez del tema de Tigrex: su .mca cambiado y su entrada en bgm_bat al dia.
""",
    "E": """E. Montana Celestial, monstruo sin tema propio: su tema de siempre, recodificado
   por el randomizer. Debe sonar igual que el original, con el loop hacia 1:41.
""",
}
README_FOOTER = "\nLos temas de los demas mapas no cambian. Anota el resultado de cada letra.\n"


def probe_T(rom: RomFS, current: Callable[[str], bytes]) -> dict[str, bytes]:
    pcm, rate, loop = seam_test()
    return replace_track(current, [TITLE_QUEUE], TITLE, encode_track(pcm, rate, loop))


def probe_A(rom: RomFS, current: Callable[[str], bytes]) -> dict[str, bytes]:
    """Points Tigrex's own stream entry at Gogmazios's track, instead of remapping the request to another
    stream index (which once left the Tigrex stream unused: see docs/music.md and `unused_streams`)."""
    battle = parse_strq(read_queue(current, BATTLE))
    request = next(r for r in battle["requests"] if r["id"] == TIGREX_REQUEST)
    battle["streams"][request["stream"]] = stream_entry(GOGMAZIOS, rom.read(romfs_path(GOGMAZIOS)))
    return queue_files(current, BATTLE, build_strq(battle))


def probe_B(rom: RomFS, current: Callable[[str], bytes]) -> dict[str, bytes]:
    st01 = "sound\\bgm\\stage\\bgm_st_01"
    queue = parse_strq(read_queue(current, st01))
    queue["streams"][FIELD_STREAM] = stream_entry(UKANLOS, rom.read(romfs_path(UKANLOS)))
    return queue_files(current, st01, build_strq(queue))


def probe_C(rom: RomFS, current: Callable[[str], bytes]) -> dict[str, bytes]:
    st02 = "sound\\bgm\\stage\\bgm_st_02"
    target = parse_strq(read_queue(current, st02))["streams"][FIELD_STREAM]["path"]
    return replace_track(current, [st02], target, rom.read(romfs_path(SEREGIOS)))


def probe_D(rom: RomFS, current: Callable[[str], bytes]) -> dict[str, bytes]:
    st03 = "sound\\bgm\\stage\\bgm_st_03"
    target = parse_strq(read_queue(current, st03))["streams"][FIELD_STREAM]["path"]
    return {romfs_path(target): encode_track(*seam_test())}


def probe_M(rom: RomFS, current: Callable[[str], bytes]) -> dict[str, bytes]:
    return replace_track(current, [BATTLE], TIGREX, encode_track(*seam_test()))


def probe_E(rom: RomFS, current: Callable[[str], bytes]) -> dict[str, bytes]:
    import numpy as np
    st05 = "sound\\bgm\\stage\\bgm_st_05"
    target = parse_strq(read_queue(current, st05))["streams"][FIELD_STREAM]["path"]
    retail = parse_madp(rom.read(romfs_path(target)))
    mca = encode_track(np.array(decode_madp(retail), dtype=float), retail.rate, (retail.loop_start, retail.loop_end))
    return replace_track(current, [st05], target, mca)


PROBES = {"T": probe_T, "A": probe_A, "B": probe_B, "C": probe_C, "D": probe_D, "E": probe_E, "M": probe_M}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--probes", default="TBCDE", help=f"checks to include, any of {''.join(PROBES)} (default: "
                                                           "TBCDE; A is left out, see the module docstring)")
    parser.add_argument("--base", type=Path, help="mod folder whose ARCs to patch (default: the game's)")
    parser.add_argument("--rom", type=Path, help="decrypted .3ds (default: the GUI's ROM)")
    args = parser.parse_args()
    letters = list(args.probes.upper())
    unknown = [letter for letter in letters if letter not in PROBES]
    if unknown:
        raise SystemExit(f"unknown probe(s) {unknown}, choose from {''.join(PROBES)}")
    rom, update = open_game(args.rom)
    read = mod_reader([args.base] if args.base else [], rom, update)
    files: dict[str, bytes] = {}

    def current(path: str) -> bytes:
        return files[path] if path in files else read(path)

    for letter in letters:
        print(letter)
        files.update(PROBES[letter](rom, current))

    write_files(args.out, files)
    readme = README_HEADER + "".join(README_LETTERS[letter] for letter in letters) + README_FOOTER
    (args.out / "LEEME.txt").write_text(readme, encoding="utf-8")


if __name__ == "__main__":
    main()
