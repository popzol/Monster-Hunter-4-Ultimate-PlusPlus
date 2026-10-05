"""Declarative description of the GUI option panels.

The window is generated from `SECTIONS`: each section is a tab, each group a
titled box, each option a widget bound to a `Settings` field. To expose a new
setting, add an `Option` here; `tests/test_gui_options.py` fails if a
`Settings` field is missing or an enum value has no label.

This module must not import tkinter, so it can be tested headless.
"""

from dataclasses import dataclass, field
from enum import Enum

from ..randomizer.settings import (
    DuplicateMode, Frequency, ProgressionMode, RewardSource, StructureMode, SubQuestMode, TextMode,
)


@dataclass(frozen=True)
class Choice:
    value: Enum
    label: str
    tooltip: str = ""


@dataclass(frozen=True)
class Option:
    field: str                       # Settings attribute
    label: str
    tooltip: str = ""
    choices: tuple[Choice, ...] = ()  # radio buttons for enum fields
    minimum: int = 0                 # spin boxes for int fields
    maximum: int = 0
    requires: str | None = None      # bool Settings field that must be on for this option to apply


@dataclass(frozen=True)
class Group:
    title: str
    options: tuple[Option, ...]


@dataclass(frozen=True)
class Section:
    title: str
    groups: tuple[Group, ...] = field(default_factory=tuple)


SECTIONS: tuple[Section, ...] = (
    Section("Monstruos grandes", (
        Group("Monstruos", (
            Option("randomize_monsters", "Randomizar monstruos grandes",
                   "Sustituye los monstruos grandes de cada misión respetando las reglas del motor."),
        )),
        Group("Estructura de oleadas", (
            Option("structure", "", requires="randomize_monsters", choices=(
                Choice(StructureMode.KEEP, "Mantener la original",
                       "Mismas oleadas y mismo número de monstruos por oleada."),
                Choice(StructureMode.KEEP_PROGRESSION, "Mantener solo en Key y Urgentes",
                       "Las misiones necesarias para subir de rango conservan su estructura; el resto es aleatoria."),
                Choice(StructureMode.RANDOM, "Aleatoria",
                       "Número de oleadas y de monstruos por oleada al azar."),
            )),
        )),
        Group("Monstruos repetidos", (
            Option("duplicates", "", requires="randomize_monsters", choices=(
                Choice(DuplicateMode.ONLY_IF_ORIGINAL, "Solo si la original los repetía",
                       "Las misiones de '2 Tigrex' siguen siendo de dos iguales; en el resto, todos distintos."),
                Choice(DuplicateMode.NEVER, "Nunca", "Siempre monstruos distintos."),
                Choice(DuplicateMode.ALLOWED, "Permitidos", "El mismo monstruo puede salir varias veces."),
            )),
        )),
        Group("Progresión de dificultad", (
            Option("progression", "", requires="randomize_monsters", choices=(
                Choice(ProgressionMode.PROGRESSIVE, "Progresiva",
                       "Tiers ponderados según el rango de la misión."),
                Choice(ProgressionMode.BALANCED, "Equilibrada",
                       "Cada monstruo se sustituye por otro de tier parecido (±2)."),
                Choice(ProgressionMode.NONE, "Sin progresión", "Cualquier monstruo en cualquier misión."),
            )),
            Option("adjust_stats", "Ajustar vida y ataque al tier (provisional)",
                   "Baja o sube la vida y el ataque según la diferencia de tier con el monstruo original.",
                   requires="randomize_monsters"),
        )),
    )),
    Section("Mapas", (
        Group("Mapas", (
            Option("randomize_maps", "Randomizar mapas",
                   "Mueve las misiones a otros mapas, con los monstruos pequeños y ajustes de ese mapa."),
            Option("always_music", "Evitar mapas sin música",
                   "Solo usa mapas sin música de zona si todos los monstruos tienen su propio tema.",
                   requires="randomize_maps"),
            Option("one_monster_per_wave_on_arenas", "Un monstruo por oleada en arenas",
                   "No mueve a una arena misiones con varios monstruos a la vez.", requires="randomize_maps"),
        )),
        Group("Arenas (mapas pequeños)", (
            Option("arena_maps", "", requires="randomize_maps", choices=(
                Choice(Frequency.NORMAL, "Sí", "Las arenas salen tanto como cualquier otro mapa."),
                Choice(Frequency.RARE, "Pocas veces", "Las arenas salen con menos frecuencia."),
                Choice(Frequency.NEVER, "No", "Nunca se mueve una misión a una arena."),
            )),
        )),
        Group("Bosque Eterno (Everwood)", (
            Option("everwood", "", requires="randomize_maps", choices=(
                Choice(Frequency.NORMAL, "Sí", "Experimental: sus zonas se generan proceduralmente."),
                Choice(Frequency.RARE, "Pocas veces", "Experimental."),
                Choice(Frequency.NEVER, "No", "Recomendado mientras no se pruebe en el juego."),
            )),
        )),
    )),
    Section("Objetivos y textos", (
        Group("Submisiones", (
            Option("sub_quests", "", choices=(
                Choice(SubQuestMode.RANDOMIZE, "Romper una parte",
                       "La submisión pide romper una parte de uno de los monstruos de la misión."),
                Choice(SubQuestMode.DISABLE, "Desactivar", "Las misiones no tienen submisión."),
            )),
        )),
        Group("Textos de la misión", (
            Option("text", "", choices=(
                Choice(TextMode.REPLACE_NAMES, "Sustituir nombres",
                       "Cambia los nombres de los monstruos en título, objetivo y descripción (5 idiomas)."),
                Choice(TextMode.LIST_MONSTERS, "\"Te enfrentarás a: …\"",
                       "El objetivo principal lista los monstruos de la misión."),
                Choice(TextMode.KEEP, "No tocar", "El tablón muestra los textos originales."),
            )),
        )),
    )),
    Section("Recompensas y suministros", (
        Group("Recompensas", (
            Option("randomize_rewards", "Randomizar recompensas",
                   "Las cajas de recompensa dan materiales de monstruo en su cantidad máxima."),
            Option("reward_source", "", requires="randomize_rewards", choices=(
                Choice(RewardSource.QUEST_MONSTERS_AND_RANK, "Monstruos de la misión + rango",
                       "Parte de los materiales son de los monstruos de la misión."),
                Choice(RewardSource.RANK, "Cualquiera del rango",
                       "Materiales al azar de la rareza del rango de la misión."),
            )),
            Option("reward_item_count", "Materiales distintos por caja", minimum=1, maximum=15,
                   requires="randomize_rewards"),
        )),
        Group("Suministros", (
            Option("randomize_supplies", "Randomizar suministros",
                   "Cada hueco de la caja de suministros pasa a ser un consumible al máximo. "
                   "El Mapa se conserva."),
        )),
    )),
    Section("Otros monstruos", (
        Group("Monstruos pequeños", (
            Option("randomize_small_monsters", "Randomizar monstruos pequeños",
                   "Cambia especies pequeñas dentro de su grupo (herbívoros, raptores, voladores)."),
        )),
        Group("Intrusos", (
            Option("randomize_intruders", "Randomizar intrusos",
                   "Cambia los monstruos que pueden invadir la misión (nunca dragones de final ni con cinemática)."),
        )),
    )),
    Section("Depuración", (
        Group("Pruebas", (
            Option("debug_weak_monsters", "Monstruos débiles",
                   "Vida y ataque al mínimo en todos los monstruos, para probar misiones rápido."),
        )),
    )),
)


def all_options() -> list[Option]:
    return [option for section in SECTIONS for group in section.groups for option in group.options]
