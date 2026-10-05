"""Declarative description of the GUI option panels.

The window is generated from `SECTIONS`: each section is a tab, each group a
titled card, each option a widget bound to a `Settings` field. To expose a new
setting, add an `Option` here; `tests/test_gui_options.py` fails if a
`Settings` field is missing, an enum value has no choice or a text is not
translated.

This module must not import tkinter, so it can be tested headless.
"""

from dataclasses import dataclass
from enum import Enum

from ..randomizer.settings import (
    DuplicateMode, Frequency, ProgressionMode, RewardSource, StructureMode, SubQuestMode, TextMode,
)
from .i18n import EMPTY, T


@dataclass(frozen=True)
class Choice:
    value: Enum
    label: T
    tooltip: T = EMPTY


@dataclass(frozen=True)
class Option:
    field: str                       # Settings attribute
    label: T = EMPTY
    tooltip: T = EMPTY
    choices: tuple[Choice, ...] = ()  # radio buttons for enum fields
    minimum: int = 0                 # stepper for int fields
    maximum: int = 0
    requires: str | None = None      # bool Settings field that must be on for this option to apply


@dataclass(frozen=True)
class Group:
    title: T
    options: tuple[Option, ...]
    description: T = EMPTY


@dataclass(frozen=True)
class Section:
    title: T
    groups: tuple[Group, ...]


SECTIONS: tuple[Section, ...] = (
    Section(T("Monstruos grandes", "Large monsters"), (
        Group(T("Monstruos", "Monsters"), (
            Option("randomize_monsters", T("Randomizar monstruos grandes", "Randomize large monsters"),
                   T("Sustituye los monstruos grandes de cada misión respetando las reglas del motor del juego.",
                     "Replaces the large monsters of every quest while respecting the game engine's rules.")),
        ), T("Dragones de final, monstruos con cinemática y Dalamadur se colocan siempre donde el juego los admite.",
             "Finale dragons, cutscene monsters and Dalamadur are always placed where the game supports them.")),
        Group(T("Estructura de oleadas", "Wave structure"), (
            Option("structure", requires="randomize_monsters", choices=(
                Choice(StructureMode.KEEP, T("Mantener la original", "Keep the original"),
                       T("Mismo número de oleadas y de monstruos por oleada que la misión original.",
                         "Same number of waves and monsters per wave as the original quest.")),
                Choice(StructureMode.KEEP_PROGRESSION, T("Mantener solo en misiones clave", "Keep only in key quests"),
                       T("Las misiones clave y urgentes conservan su estructura; el resto se genera al azar.",
                         "Key and urgent quests keep their structure; all others are generated at random.")),
                Choice(StructureMode.RANDOM, T("Aleatoria", "Random"),
                       T("Número de oleadas y de monstruos por oleada al azar.",
                         "Random number of waves and monsters per wave.")),
            )),
        )),
        Group(T("Monstruos repetidos", "Repeated monsters"), (
            Option("duplicates", requires="randomize_monsters", choices=(
                Choice(DuplicateMode.ONLY_IF_ORIGINAL, T("Solo si la original los repetía", "Only where the original did"),
                       T("Las misiones de dos monstruos iguales siguen siéndolo; en el resto, todos son distintos.",
                         "Quests with two identical monsters keep that pattern; elsewhere every monster is different.")),
                Choice(DuplicateMode.NEVER, T("Nunca", "Never"),
                       T("Todos los monstruos de una misión son distintos.", "Every monster in a quest is different.")),
                Choice(DuplicateMode.ALLOWED, T("Permitidos", "Allowed"),
                       T("El mismo monstruo puede aparecer varias veces.", "The same monster may appear several times.")),
            )),
        )),
        Group(T("Progresión de dificultad", "Difficulty progression"), (
            Option("progression", requires="randomize_monsters", choices=(
                Choice(ProgressionMode.PROGRESSIVE, T("Progresiva", "Progressive"),
                       T("La dificultad de los monstruos se pondera según el rango de la misión.",
                         "Monster difficulty is weighted by the quest's rank.")),
                Choice(ProgressionMode.BALANCED, T("Equilibrada", "Balanced"),
                       T("Cada monstruo se sustituye por otro de dificultad similar (±2 niveles).",
                         "Each monster is replaced by one of similar difficulty (±2 tiers).")),
                Choice(ProgressionMode.NONE, T("Sin progresión", "No progression"),
                       T("Cualquier monstruo puede aparecer en cualquier misión.",
                         "Any monster can appear in any quest.")),
            )),
            Option("adjust_stats", T("Ajustar vida y ataque a la dificultad", "Scale health and attack to difficulty"),
                   T("Compensa la vida y el ataque según la diferencia de dificultad con el monstruo sustituido. "
                     "Fórmula provisional.",
                     "Compensates health and attack for the difficulty gap with the replaced monster. "
                     "Provisional formula."),
                   requires="randomize_monsters"),
        )),
    )),
    Section(T("Mapas", "Maps"), (
        Group(T("Mapas", "Maps"), (
            Option("randomize_maps", T("Randomizar mapas", "Randomize maps"),
                   T("Traslada las misiones a otros mapas junto con sus monstruos pequeños y ajustes de zona.",
                     "Moves quests to other maps together with their small monsters and area settings.")),
            Option("always_music", T("Evitar mapas sin música", "Avoid maps without music"),
                   T("Solo usa mapas sin música de zona si todos los monstruos tienen su propio tema.",
                     "Only uses maps without area music if every monster has its own theme."),
                   requires="randomize_maps"),
            Option("one_monster_per_wave_on_arenas", T("Un monstruo por oleada en arenas", "One monster per wave in arenas"),
                   T("No traslada a una arena las misiones con varios monstruos simultáneos.",
                     "Does not move quests with simultaneous monsters to an arena."),
                   requires="randomize_maps"),
        )),
        Group(T("Arenas", "Arenas"), (
            Option("arena_maps", requires="randomize_maps", choices=(
                Choice(Frequency.NORMAL, T("Frecuentes", "Common"),
                       T("Las arenas aparecen con la misma frecuencia que cualquier otro mapa.",
                         "Arenas appear as often as any other map.")),
                Choice(Frequency.RARE, T("Ocasionales", "Occasional"),
                       T("Las arenas aparecen con menos frecuencia.", "Arenas appear less often.")),
                Choice(Frequency.NEVER, T("Nunca", "Never"),
                       T("Ninguna misión se traslada a una arena.", "No quest is moved to an arena.")),
            )),
        ), T("Mapas pequeños de una sola zona, como la Arena o el Gran Mar.",
             "Small single-area maps, such as the Arena or the Great Sea.")),
        Group(T("Bosque Eterno", "Everwood"), (
            Option("everwood", requires="randomize_maps", choices=(
                Choice(Frequency.NORMAL, T("Frecuente", "Common"),
                       T("Experimental: las zonas del Bosque Eterno se generan proceduralmente.",
                         "Experimental: Everwood areas are generated procedurally.")),
                Choice(Frequency.RARE, T("Ocasional", "Occasional"), T("Experimental.", "Experimental.")),
                Choice(Frequency.NEVER, T("Nunca", "Never"),
                       T("Recomendado hasta que se compruebe en el juego.", "Recommended until verified in-game.")),
            )),
        )),
    )),
    Section(T("Objetivos y textos", "Objectives & text"), (
        Group(T("Submisiones", "Subquests"), (
            Option("sub_quests", choices=(
                Choice(SubQuestMode.RANDOMIZE, T("Romper una parte", "Break a part"),
                       T("La submisión consiste en romper una parte de uno de los monstruos de la misión.",
                         "The subquest asks you to break a part of one of the quest's monsters.")),
                Choice(SubQuestMode.DISABLE, T("Desactivadas", "Disabled"),
                       T("Las misiones no tienen submisión.", "Quests have no subquest.")),
            )),
        )),
        Group(T("Textos de las misiones", "Quest text"), (
            Option("text", choices=(
                Choice(TextMode.REPLACE_NAMES, T("Sustituir nombres", "Replace names"),
                       T("Actualiza los nombres de los monstruos en título, objetivo y descripción, en los cinco idiomas.",
                         "Updates monster names in title, objective and description, in all five languages.")),
                Choice(TextMode.LIST_MONSTERS, T("Listar los monstruos", "List the monsters"),
                       T("El objetivo principal muestra «Te enfrentarás a:» seguido de los monstruos.",
                         "The main objective shows “You will face:” followed by the monsters.")),
                Choice(TextMode.KEEP, T("Sin cambios", "Unchanged"),
                       T("El tablón muestra los textos originales.", "The quest board shows the original text.")),
            )),
        )),
    )),
    Section(T("Recompensas y suministros", "Rewards & supplies"), (
        Group(T("Recompensas", "Rewards"), (
            Option("randomize_rewards", T("Randomizar recompensas", "Randomize rewards"),
                   T("Las cajas de recompensa entregan materiales de monstruo en su cantidad máxima.",
                     "Reward boxes hand out monster materials in their maximum quantity.")),
            Option("reward_source", requires="randomize_rewards", choices=(
                Choice(RewardSource.QUEST_MONSTERS_AND_RANK, T("Monstruos de la misión y rango", "Quest monsters and rank"),
                       T("Parte de los materiales procede de los monstruos de la propia misión.",
                         "Part of the materials comes from the quest's own monsters.")),
                Choice(RewardSource.RANK, T("Cualquiera del rango", "Any from the rank"),
                       T("Materiales al azar con la rareza del rango de la misión.",
                         "Random materials with the rarity of the quest's rank.")),
            )),
            Option("reward_item_count", T("Materiales distintos por caja", "Different materials per box"),
                   T("Número de materiales distintos en cada caja de recompensa.",
                     "Number of different materials in each reward box."),
                   minimum=1, maximum=15, requires="randomize_rewards"),
        )),
        Group(T("Suministros", "Supplies"), (
            Option("randomize_supplies", T("Randomizar suministros", "Randomize supplies"),
                   T("Cada hueco de la caja de suministros contiene un consumible al azar en su cantidad máxima. "
                     "El mapa se conserva siempre.",
                     "Each supply box slot holds a random consumable in its maximum quantity. "
                     "The map is always kept.")),
        )),
    )),
    Section(T("Otros monstruos", "Other monsters"), (
        Group(T("Monstruos pequeños", "Small monsters"), (
            Option("randomize_small_monsters", T("Randomizar monstruos pequeños", "Randomize small monsters"),
                   T("Intercambia especies pequeñas dentro de su grupo: herbívoros, raptores e insectos.",
                     "Swaps small species within their group: herbivores, raptors and insects.")),
        )),
        Group(T("Intrusos", "Intruders"), (
            Option("randomize_intruders", T("Randomizar intrusos", "Randomize intruders"),
                   T("Cambia los monstruos que pueden irrumpir en la misión. Nunca se usan dragones de final "
                     "ni monstruos con cinemática.",
                     "Changes the monsters that may intrude on the quest. Finale dragons and cutscene monsters "
                     "are never used.")),
        )),
    )),
    Section(T("Depuración", "Debug"), (
        Group(T("Pruebas", "Testing"), (
            Option("debug_weak_monsters", T("Monstruos débiles", "Weak monsters"),
                   T("Vida y ataque al mínimo en todos los monstruos, para probar misiones rápidamente.",
                     "Minimum health and attack for every monster, to test quests quickly.")),
        ), T("Opciones pensadas para probar el randomizer, no para jugar.",
             "Options meant for testing the randomizer, not for playing.")),
    )),
)


def all_options() -> list[Option]:
    return [option for section in SECTIONS for group in section.groups for option in group.options]


def all_texts() -> list[T]:
    """Every translatable text of the option panels (for tests)."""
    texts = []
    for section in SECTIONS:
        texts.append(section.title)
        for group in section.groups:
            texts.append(group.title)
            if group.description is not EMPTY:
                texts.append(group.description)
            for option in group.options:
                texts += [t for t in (option.label, option.tooltip) if t is not EMPTY]
                for choice in option.choices:
                    texts += [t for t in (choice.label, choice.tooltip) if t is not EMPTY]
    return texts
