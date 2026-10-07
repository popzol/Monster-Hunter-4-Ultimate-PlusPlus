"""Build a HUD test mod for Citra (see docs/hud_layout.md).

    python tools/hud_probe.py ROM --out DIR [--update UPDATE.app] [--scale 70] [--tint]
                              [--minimap [--merge-ips CURRENT.ips] [--target-button
                              [--target-asm ROUTINE.s --devkitarm DIR]] [--target-face [--face-debug]]]

ROM is the decrypted .3ds. UPDATE is the update's 00000000.app, needed for the
core_common.arc layouts because the update replaces that file. Default: every
known HUD layout scaled (mh4u_rando/hud/build.py). --minimap also shrinks what
needs the executable patch (minimap, map icons, mount gauge) and, with UPDATE,
writes exefs/code.ips with it (mh4u_rando/hud/code_patch.py); --merge-ips keeps the changes of another
code.ips (e.g. the randomizer's equipment patch) in it. --tint: the first probe
instead (main HUD scaled, other candidate layouts tinted to identify them).
--target-button adds the L + X target switch; --target-asm assembles another
routine in its place (a diagnostic one such as tools/asm/input_event_log.s,
read back with tools/citra_state.py; needs devkitARM or the Arm GNU Toolchain).
--target-face shows the target panel's monster faces on the top screen too;
--face-debug builds its diagnostic version instead, which writes a snapshot
every frame (read with tools/citra_state.py --face-dump; needs the compiler).
Writes DIR/romfs/..., DIR/exefs/code.ips and DIR/LEEME.txt; copy romfs and exefs
into load/mods/0004000000126100/.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mh4u_rando.arc import parse_arc, write_arc  # noqa: E402
from mh4u_rando.exefs import RomFS, apply_ips, load_code, make_ips  # noqa: E402
from mh4u_rando.hud import LANGUAGES, LYT_TYPE_HASH, Anchor, hud_files, parse_lyt, scale_arc  # noqa: E402
from mh4u_rando.hud.build import MAP_ARC, short_name  # noqa: E402
from mh4u_rando.hud.code_patch import (  # noqa: E402
    BASE_ADDRESS, CAVE, CAVE_END, FACE_HOOK, FACE_ROUTINE, FREE_HOOK, ICON_CALLS, LOADER_HOOK, MOUNT_FACE_FLOATS,
    TARGET_BUTTON, TARGET_ROUTINE, TARGET_TEST, patch_hud, patch_target_button, patch_target_face,
)
from build_hud_asm import ASM, DEFAULT_DEVKITARM, assemble  # noqa: E402

TINTS = {
    "core_quest.arc": {"ui203": ("rojo", (255, 40, 40)), "ui204": ("verde", (40, 220, 40)),
                       "ui205": ("azul", (50, 80, 255)), "ui206": ("naranja", (255, 140, 0)),
                       "ui250": ("magenta", (255, 0, 255))},
    "core_common.arc": {"ui001": ("amarillo", (255, 240, 0)), "ui007": ("cian", (0, 230, 230)),
                        "ui000": ("rosa", (255, 150, 200))},
}
MAP_TINT = ("negro", (0, 0, 0))
INSTALL = [
    "Instalación en Citra: copia la carpeta \"romfs\" dentro de",
    "   %APPDATA%\\Citra\\load\\mods\\0004000000126100\\",
    "Se suma al romfs\\loc del randomizer sin pisar nada. Para quitarlo, borra",
    "romfs\\eng, romfs\\fre, romfs\\ger, romfs\\ita y romfs\\spa.",
    "",
]


def tint(layout, rgb: tuple[int, int, int]) -> None:
    """Paint every sprite and text of the layout, keeping each corner's alpha."""
    for pane in layout.panes:
        if pane.colors is not None:
            pane.colors = [(*rgb, alpha) for *_, alpha in pane.colors]


def tint_arc(raw: bytes, tints: dict[str, tuple[int, int, int]]) -> bytes:
    arc = parse_arc(raw)
    for entry in arc.entries:
        if entry.type_hash == LYT_TYPE_HASH and short_name(entry.name) in tints:
            layout = parse_lyt(entry.data)
            tint(layout, tints[short_name(entry.name)])
            entry.data = layout.to_bytes()
    return write_arc(arc)


def tint_files(rom: RomFS, update: RomFS | None, factor: float):
    """First probe: ui202 scaled towards the top-left corner, other candidates tinted."""
    map_paths = [p for p in rom.walk() if p.split("/")[0] in LANGUAGES and MAP_ARC.fullmatch(p.split("/")[-1])]
    for lang in LANGUAGES:
        path = f"{lang}/data/core_quest.arc"
        raw = scale_arc(rom.read(path), {"ui202": Anchor.TOP_LEFT}, factor)
        yield path, tint_arc(raw, {name: rgb for name, (_, rgb) in TINTS["core_quest.arc"].items()})
        if update is not None:
            path = f"{lang}/data/core_common.arc"
            yield path, tint_arc(update.read(path), {name: rgb for name, (_, rgb) in TINTS["core_common.arc"].items()})
        for path in map_paths:
            if path.startswith(lang + "/"):
                raw = rom.read(path)
                names = [short_name(e.name) for e in parse_arc(raw).entries if e.type_hash == LYT_TYPE_HASH]
                yield path, tint_arc(raw, {name: MAP_TINT[1] for name in names})


def tint_readme(scale: int, with_common: bool) -> list[str]:
    legend = [f"   {color:9} = {name}" for arc, layouts in TINTS.items()
              if arc != "core_common.arc" or with_common for name, (color, _) in layouts.items()]
    legend.append(f"   {MAP_TINT[0]:9} = layouts de los mapas (mNN_map)")
    return [
        "Prueba 1 del tamaño del HUD: identificar los layouts. No es el mod final.", "", *INSTALL,
        f"1. HUD principal (reloj, vida, aguante, filo, medidores del arma) al {scale} %,",
        "   hacia la esquina superior izquierda.",
        "2. Otros layouts teñidos de un color para saber qué es cada uno:", *legend, "",
        "Qué mirar en una misión:",
        "- ¿El HUD principal sale más pequeño y pegado arriba a la izquierda, o se va a otro sitio?",
        "- Vida y aguante: recibe daño, cúrate, come carne, deja que baje el aguante máximo.",
        "  ¿El relleno sigue dentro de su marco?",
        "- Qué sale de cada color en la pantalla superior, y si algo se tiñe en la táctil.",
        "  Prueba con y sin el minimapa en la pantalla superior.",
        "- Cualquier cosa rara: textos fuera de sitio, parpadeos, cuelgues.",
    ]


def scale_readme(scale: int, with_common: bool, minimap: bool, code_patch: bool) -> list[str]:
    return [
        f"Prueba del tamaño del HUD: todo el HUD superior al {scale} %. No es el mod final.", "", *INSTALL,
        *(["Esta prueba incluye exefs\\code.ips: copia también la carpeta exefs (sustituye a tu",
           "code.ips; si se generó con --merge-ips, ya incluye los cambios de ese parche).", ""]
          if code_patch else []),
        "Qué se reduce:",
        "- Reloj, vida, aguante, filo y medidores del arma: hacia arriba a la izquierda.",
        "- Lista del grupo y el icono del virus: hacia arriba a la izquierda.",
        "- Selector de objetos y de munición: hacia abajo a la derecha.",
        "- Medidores de agarrar y pescar: hacia abajo, centrados"
        + (", y el de montar con su cara (parche del ejecutable)." if code_patch else " (el de montar no)."),
        *(["- Avisos sobre los personajes (trepar...) y sus nombres: cada uno en su sitio."] if with_common else []),
        *(["- El minimapa, hacia arriba a la derecha" +
           (", con sus iconos más pequeños (parche del ejecutable)." if code_patch else
            " (sus iconos NO lo siguen).")]
          if minimap else []),
        "",
        "Qué mirar en una misión:",
        *(["- Minimapa con el objeto Mapa: ¿los iconos (tú, compañeros, monstruos, trampas)",
           "  están encima de su sitio y con un tamaño proporcionado? Mira también el mapa de la",
           "  pantalla táctil y, si puedes, una zona de las Ruinas antiguas (Everwood).",
           "- Montar a un monstruo: ¿la cara del monstruo recorre la barra sin salirse?",
           "- ¿El juego va igual de fluido? ¿Algún cuelgue?"] if minimap else []),
        "- Selector de objetos, lista del grupo, avisos y nombres sobre los personajes.",
        "- Cualquier cosa del HUD superior que siga grande, y cualquier cosa rara.",
    ]


def without_hud_patch(code: bytes, original: bytes) -> bytes:
    """`code` with the original bytes back wherever code_patch.patch_hud writes."""
    out = bytearray(code)
    spans = [(CAVE, CAVE_END)] + [(site, site + 4) for site in ICON_CALLS] + \
        [(address, address + 4) for address in MOUNT_FACE_FLOATS] + [(TARGET_TEST, TARGET_TEST + 16)] + \
        [(LOADER_HOOK, LOADER_HOOK + 4), (FREE_HOOK, FREE_HOOK + 4), (FACE_HOOK, FACE_HOOK + 4)]
    for start, end in spans:
        out[start - BASE_ADDRESS:end - BASE_ADDRESS] = original[start - BASE_ADDRESS:end - BASE_ADDRESS]
    return bytes(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--update", type=Path)
    parser.add_argument("--scale", type=int, default=70)
    parser.add_argument("--tint", action="store_true")
    parser.add_argument("--minimap", action="store_true")
    parser.add_argument("--merge-ips", type=Path, help="code.ips whose changes are kept in the new one")
    parser.add_argument("--target-button", action="store_true", help="also L + X to switch the target")
    parser.add_argument("--target-asm", type=Path, help="routine assembled instead of asm/target_button.s")
    parser.add_argument("--devkitarm", type=Path, default=DEFAULT_DEVKITARM, help="bin folder of the assembler")
    parser.add_argument("--target-face", action="store_true", help="also the target's face on the top screen")
    parser.add_argument("--face-debug", action="store_true",
                        help="the target face's diagnostic build (snapshot for citra_state.py --face-dump)")
    args = parser.parse_args()
    factor = args.scale / 100
    rom = RomFS(args.rom)
    update = RomFS(args.update) if args.update else None
    files = tint_files(rom, update, factor) if args.tint else \
        hud_files(rom, update, factor, with_code_patch=args.minimap)
    count = 0
    for path, data in files:
        target = args.out / "romfs" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        count += 1
    code_patch = args.minimap and not args.tint and update is not None
    if code_patch:
        original = load_code(args.update)
        code = apply_ips(original, args.merge_ips.read_bytes()) if args.merge_ips else original
        code = without_hud_patch(code, original)  # the merged patch may come from an earlier probe
        ips = args.out / "exefs" / "code.ips"
        ips.parent.mkdir(parents=True, exist_ok=True)
        code = patch_hud(code, factor)
        if args.target_button:
            routine = assemble(args.target_asm, TARGET_ROUTINE, args.devkitarm) if args.target_asm else TARGET_BUTTON
            code = patch_target_button(code, routine)
        if args.target_face and args.face_debug:
            routine = assemble(ASM / "target_face.c", FACE_ROUTINE, args.devkitarm, ("FACE_DEBUG",))
            code = patch_target_face(code, factor, routine)
        elif args.target_face:
            code = patch_target_face(code, factor)
        ips.write_bytes(make_ips(original, code))
        print(f"HUD executable patch written to {ips}")
    readme = tint_readme(args.scale, update is not None) if args.tint else \
        scale_readme(args.scale, update is not None, args.minimap, code_patch)
    (args.out / "LEEME.txt").write_text("\n".join(readme) + "\n", encoding="utf-8")
    print(f"{count} files written to {args.out / 'romfs'}")


if __name__ == "__main__":
    main()
