"""Declarative description of the GUI option panels.

The window is generated from `AREAS`: each area (quests, equipment) is a tab
of the first row, each of its sections a tab of the second row, each group a
titled card and each option a widget bound to a `Settings` field. To expose a new
setting, add an `Option` here; `tests/test_gui_options.py` fails if a
`Settings` field is missing, an enum value has no choice or a text is not
translated.

This module must not import tkinter, so it can be tested headless.
"""

from dataclasses import dataclass
from enum import Enum

from ..randomizer.settings import (
    ArmorSkillMode, DuplicateMode, Frequency, HudScale, ModelMode, PalicoModelMode, ProgressionMode, RewardSource,
    StatMode, StructureMode, SubQuestMode, TextMode,
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
    requires: str | None = None      # Settings field that must be on (bool) or not on its first choice (enum)
    compact: bool = False            # enum shown as a labelled drop-down instead of radio buttons
    range_to: str | None = None      # int pair "between N and M": `field` is N, this Settings field is M


@dataclass(frozen=True)
class Group:
    title: T
    options: tuple[Option, ...]
    description: T = EMPTY


@dataclass(frozen=True)
class Section:
    title: T
    groups: tuple[Group, ...]


@dataclass(frozen=True)
class Area:
    """First row of tabs (quests / equipment); its sections are the second row."""
    title: T
    sections: tuple[Section, ...]


STAT_CHOICES = (
    Choice(StatMode.KEEP, T("No cambiar", "Don't change"),
           T("Se conserva el valor del juego original.", "The original game's value is kept.")),
    Choice(StatMode.PERCENT, T("Progresivo", "Progressive"),
           T("Cambio de hasta un 20 %, casi siempre pequeño, así que el equipo sigue mejorando al avanzar. "
             "Un valor 0 sigue siendo 0.",
             "A change of up to 20%, usually small, so gear still improves as you progress. A value of 0 stays 0.")),
    Choice(StatMode.RANGE, T("Aleatorio", "Random"),
           T("Cualquier valor entre el mínimo y el máximo de ese tipo de equipo en el mismo rango (bajo, alto o G) "
             "del juego original.",
             "Any value between the minimum and maximum of that kind of equipment in the same rank (low, high "
             "or G) of the original game.")),
)
STAT_MODES_HELP = T(
    "Progresivo: cambio de hasta un 20 %, casi siempre pequeño, así que el equipo sigue mejorando al avanzar. "
    "Aleatorio: cualquier valor entre el mínimo y el máximo de ese tipo de equipo en el mismo rango (bajo, alto "
    "o G) del juego original.",
    "Progressive: a change of up to 20%, usually small, so gear still improves as you progress. Random: any value "
    "between the minimum and maximum of that kind of equipment in the same rank (low, high or G) of the original "
    "game.")


def materials_range(prefix: str, requires: str) -> Option:
    return Option(f"{prefix}_min", T("Materiales distintos", "Different materials"),
                  T("Cada receta pide entre N y M materiales distintos (como mucho 4; las mejoras de glaive insecto "
                    "admiten 2). Se recomienda entre 1 y 4.",
                    "Every recipe asks for between N and M different materials (at most 4; Insect Glaive upgrades "
                    "hold 2). Between 1 and 4 is recommended."),
                  minimum=1, maximum=4, requires=requires, range_to=f"{prefix}_max")


def quantity_range(prefix: str, requires: str) -> Option:
    return Option(f"{prefix}_min", T("Cantidad de cada material", "Quantity of each material"),
                  T("Cada material se pide entre N y M veces (como mucho 10).",
                    "Each material is asked between N and M times (at most 10)."),
                  minimum=1, maximum=10, requires=requires, range_to=f"{prefix}_max")


def stat(field: str, label: T, requires: str, tooltip: T = EMPTY) -> Option:
    return Option(field, label, tooltip, choices=STAT_CHOICES, requires=requires, compact=True)


QUEST_SECTIONS: tuple[Section, ...] = (
    Section(T("Monstruos grandes", "Large monsters"), (
        Group(T("Monstruos", "Monsters"), (
            Option("randomize_monsters", T("Randomizar monstruos grandes", "Randomize large monsters"),
                   T("Sustituye los monstruos grandes de cada misión respetando las reglas del motor del juego.",
                     "Replaces the large monsters of every quest while respecting the game engine's rules.")),
        ), T("Dragones de final, monstruos con cinemática y Dalamadur se colocan siempre donde el juego los admite.",
             "Finale dragons, cutscene monsters and Dalamadur are always placed where the game supports them.")),
        Group(T("Estructura de oleadas", "Wave structure"), (
            Option("structure", requires="randomize_monsters", choices=(
                Choice(StructureMode.KEEP, T("Mantener la original", "Don't change"),
                       T("Mismo número de oleadas y de monstruos por oleada que la misión original.",
                         "Same number of waves and monsters per wave as the original quest.")),
                Choice(StructureMode.KEEP_PROGRESSION, T("Mantener solo en misiones clave", "Don't change in key quests"),
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
                Choice(ProgressionMode.BALANCED, T("Equilibrada", "Balanced"),
                       T("Cada monstruo se sustituye por otro de dificultad similar (±2 niveles).",
                         "Each monster is replaced by one of similar difficulty (±2 tiers).")),
                Choice(ProgressionMode.PROGRESSIVE, T("Progresiva", "Progressive"),
                       T("La dificultad de los monstruos se pondera según el rango de la misión.",
                         "Monster difficulty is weighted by the quest's rank.")),
                Choice(ProgressionMode.NONE, T("Sin progresión", "No progression"),
                       T("Cualquier monstruo puede aparecer en cualquier misión.",
                         "Any monster can appear in any quest.")),
            )),
            Option("adjust_stats", T("Ajustar vida y ataque a la dificultad", "Scale health and attack to difficulty"),
                   T("Mantiene la vida del monstruo sustituido según la vida base de cada especie, y compensa el "
                     "ataque según la diferencia de dificultad. El ataque es una fórmula provisional.",
                     "Keeps the replaced monster's health using each species' base health, and compensates "
                     "attack for the difficulty gap. The attack formula is provisional."),
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
                Choice(Frequency.NEVER, T("Nunca", "Never"),
                       T("Ninguna misión se traslada a una arena.", "No quest is moved to an arena.")),
                Choice(Frequency.RARE, T("Ocasionales", "Occasional"),
                       T("Las arenas aparecen con menos frecuencia.", "Arenas appear less often.")),
                Choice(Frequency.NORMAL, T("Frecuentes", "Common"),
                       T("Las arenas aparecen con la misma frecuencia que cualquier otro mapa.",
                         "Arenas appear as often as any other map.")),
            )),
        ), T("Mapas pequeños de una sola zona, como la Arena o el Gran Mar.",
             "Small single-area maps, such as the Arena or the Great Sea.")),
        Group(T("Bosque Eterno", "Everwood"), (
            Option("everwood", requires="randomize_maps", choices=(
                Choice(Frequency.NEVER, T("Nunca", "Never"),
                       T("Recomendado hasta que se compruebe en el juego.", "Recommended until verified in-game.")),
                Choice(Frequency.RARE, T("Ocasional", "Occasional"), T("Experimental.", "Experimental.")),
                Choice(Frequency.NORMAL, T("Frecuente", "Common"),
                       T("Experimental: las zonas del Bosque Eterno se generan proceduralmente.",
                         "Experimental: Everwood areas are generated procedurally.")),
            )),
        )),
    )),
    Section(T("Objetivos y textos", "Objectives & text"), (
        Group(T("Submisiones", "Subquests"), (
            Option("sub_quests", choices=(
                Choice(SubQuestMode.KEEP, T("Mantener las originales", "Don't change"),
                       T("Cada misión conserva su submisión. Si su monstruo ya no está en la misión, pasa a "
                         "otro de los monstruos.",
                         "Every quest keeps its subquest. If its monster is no longer in the quest, it moves to "
                         "another of the quest's monsters.")),
                Choice(SubQuestMode.DISABLE, T("Desactivadas", "Disabled"),
                       T("Las misiones no tienen submisión.", "Quests have no subquest.")),
                Choice(SubQuestMode.RANDOMIZE, T("Romper una parte", "Break a part"),
                       T("La submisión consiste en romper una parte de uno de los monstruos de la misión.",
                         "The subquest asks you to break a part of one of the quest's monsters.")),
            )),
        )),
        Group(T("Textos de las misiones", "Quest text"), (
            Option("text", choices=(
                Choice(TextMode.KEEP, T("Sin cambios", "Don't change"),
                       T("El tablón muestra los textos originales.", "The quest board shows the original text.")),
                Choice(TextMode.REPLACE_NAMES, T("Sustituir nombres", "Replace names"),
                       T("Actualiza los nombres de los monstruos en título, objetivo y descripción, en los cinco idiomas.",
                         "Updates monster names in title, objective and description, in all five languages.")),
                Choice(TextMode.LIST_MONSTERS, T("Nuevo objetivo", "New objective"),
                       T("El objetivo principal pasa a «Caza a A» o «Caza a A y B». Con 3 o más monstruos dice "
                         "«Caza a todos los monstruos grandes» y la lista de monstruos aparece al principio de la "
                         "descripción. En los cinco idiomas.",
                         "The main objective becomes “Hunt A” or “Hunt A and B”. With 3 or more monsters it says "
                         "“Hunt all large monsters” and the list of monsters appears at the start of the "
                         "description. In all five languages.")),
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


EQUIPMENT_SECTIONS: tuple[Section, ...] = (
    Section(T("Recetas", "Recipes"), (
        Group(T("Recetas de creación y mejora", "Create and upgrade recipes"), (
            Option("randomize_recipes", T("Randomizar recetas", "Randomize recipes"),
                   T("Cada receta de creación y de mejora pide materiales de monstruo del rango del equipo, en el "
                     "número y la cantidad elegidos abajo. Las mejoras de glaive insecto solo admiten 2.",
                     "Every create and upgrade recipe asks for monster materials of the equipment's rank, in the "
                     "number and quantity chosen below. Insect Glaive upgrades only hold 2.")),
            materials_range("recipe_material_count", "randomize_recipes"),
            quantity_range("recipe_quantity", "randomize_recipes"),
        ), T("Solo se usan materiales de monstruo que el juego original ya pide en ese rango (bajo, alto o G).",
             "Only monster materials the original game already asks for in that rank (low, high or G) are used.")),
    )),
    Section(T("Armas", "Weapons"), (
        Group(T("Estadísticas", "Stats"), (
            Option("randomize_weapon_stats", T("Randomizar estadísticas de armas", "Randomize weapon stats"),
                   T("Los valores cambian en el juego y en los menús.", "Values change both in game and in the menus.")),
            stat("weapon_attack", T("Ataque", "Attack"), "randomize_weapon_stats",
                 T("Ataque del arma, el que se ve en los menús.", "Weapon attack, as shown in the menus.")),
            stat("weapon_affinity", T("Afinidad", "Affinity"), "randomize_weapon_stats",
                 T("Probabilidad de golpe crítico (negativa: golpes más débiles). Progresivo no cambia las "
                   "armas con 0 %.",
                   "Critical hit chance (negative: weaker hits). Progressive leaves weapons at 0% unchanged.")),
            stat("weapon_defense", T("Bonus de defensa", "Defense bonus"), "randomize_weapon_stats",
                 T("Defensa extra que dan algunas armas. Progresivo no se la añade a las que no la tienen.",
                   "Extra defense some weapons give. Progressive does not add it to weapons without it.")),
            stat("weapon_slots", T("Huecos de joya", "Decoration slots"), "randomize_weapon_stats",
                 T("Huecos para joyas (0 a 3). Con Progresivo, un arma con huecos gana o pierde uno de vez en "
                   "cuando.",
                   "Slots for decorations (0 to 3). With Progressive, a weapon with slots gains or loses one "
                   "now and then.")),
            stat("weapon_sharpness", T("Afilado", "Sharpness"), "randomize_weapon_stats",
                 T("Progresivo: los colores de cada perfil de afilado se alargan o acortan hasta un 20 % (los "
                   "perfiles los comparten varias armas). Aleatorio: el afilado de otra arma de la misma clase y "
                   "rango.",
                   "Progressive: the colors of each sharpness profile grow or shrink by up to 20% (profiles are "
                   "shared by several weapons). Random: the sharpness of another weapon of the same class and "
                   "rank.")),
        ), STAT_MODES_HELP),
        Group(T("Elemento y estado", "Element and status"), (
            stat("weapon_element", T("Valor", "Value"), "randomize_weapon_stats",
                 T("Valor del elemento o estado de las armas que lo tienen.",
                   "Element or status value of the weapons that have one.")),
            Option("weapon_element_type", T("Cambiar el tipo", "Change the type"),
                   T("Las armas con elemento o estado reciben otro distinto (fuego, agua, rayo, hielo, dragón, "
                     "veneno, parálisis, sueño o nitro).",
                     "Weapons with an element or status get a different one (fire, water, thunder, ice, dragon, "
                     "poison, paralysis, sleep or blast)."),
                   requires="randomize_weapon_stats"),
            Option("weapon_element_add_remove", T("Añadir y quitar", "Add and remove"),
                   T("Cualquier arma puede ganar o perder su elemento o estado, en la misma proporción que las "
                     "armas de su clase y rango en el juego original.",
                     "Any weapon may gain or lose its element or status, in the same proportion as the weapons of "
                     "its class and rank in the original game."),
                   requires="randomize_weapon_stats"),
        ), T("No afecta a las ballestas, que usan munición.", "Does not affect bowguns, which use ammo.")),
        Group(T("Mejoras", "Upgrades"), (
            Option("weapon_upgrades_improve", T("Las mejoras siempre mejoran", "Upgrades always improve"),
                   T("Cada mejora tiene más ataque que el arma de la que viene, y no menos afinidad, defensa, "
                     "huecos, afilado ni valor del mismo elemento. Si el tope del rango no deja sitio, se baja el "
                     "arma anterior.",
                     "Every upgrade has more attack than the weapon it comes from, and no less affinity, defense, "
                     "slots, sharpness or value of the same element. If the rank cap leaves no room, the previous "
                     "weapon is lowered."),
                   requires="randomize_weapon_stats"),
            Option("weapon_upgrades_keep_element", T("Las evoluciones naturales conservan el elemento",
                                                     "Natural evolutions keep the element"),
                   T("La evolución natural de un arma es la mejora que en el juego original sigue su línea (mismo "
                     "elemento o, si no, el nombre más parecido). Con esta opción hereda el elemento o estado "
                     "del arma; las demás ramas pueden cambiarlo.",
                     "A weapon's natural evolution is the upgrade that continues its line in the original game "
                     "(same element or, failing that, the most similar name). With this option it inherits the "
                     "weapon's element or status; the other branches may change it."),
                   requires="randomize_weapon_stats"),
        ), T("Ninguna estadística supera nunca el máximo original de su clase de arma y rango (bajo, alto o G).",
             "No stat ever goes above the original maximum of its weapon class and rank (low, high or G).")),
    )),
    Section(T("Armaduras", "Armor"), (
        Group(T("Estadísticas", "Stats"), (
            Option("randomize_armor_stats", T("Randomizar estadísticas de armaduras", "Randomize armor stats"),
                   T("Los valores cambian en el juego y en los menús.", "Values change both in game and in the menus.")),
            stat("armor_defense", T("Defensa", "Defense"), "randomize_armor_stats",
                 T("Defensa base de cada pieza (sin mejorar).", "Base defense of each piece (not upgraded).")),
            stat("armor_resistances", T("Resistencias elementales", "Elemental resistances"), "randomize_armor_stats",
                 T("Resistencias a fuego, agua, rayo, hielo y dragón; cada una cambia por separado.",
                   "Fire, water, thunder, ice and dragon resistances; each one changes on its own.")),
            stat("armor_slots", T("Huecos de joya", "Decoration slots"), "randomize_armor_stats",
                 T("Huecos para joyas (0 a 3). Con Progresivo, una pieza con huecos gana o pierde uno de vez en "
                   "cuando.",
                   "Slots for decorations (0 to 3). With Progressive, a piece with slots gains or loses one now "
                   "and then.")),
        ), STAT_MODES_HELP),
        Group(T("Habilidades", "Skills"), (
            Option("armor_skills", choices=(
                Choice(ArmorSkillMode.KEEP, T("No cambiar", "Don't change"),
                       T("Cada pieza conserva sus habilidades.", "Every piece keeps its skills.")),
                Choice(ArmorSkillMode.SAME_SUM, T("Misma suma de puntos", "Same point total"),
                       T("Cada pieza conserva el total de sus puntos de habilidad, repartido entre habilidades al "
                         "azar. Las piezas sin habilidades siguen sin ellas.",
                         "Every piece keeps the total of its skill points, spread over random skills. Pieces "
                         "without skills stay without them.")),
                Choice(ArmorSkillMode.CHAOTIC, T("Caótico", "Chaotic"),
                       T("Todas las piezas reciben habilidades y puntos al azar; los valores altos son cada vez "
                         "más raros.",
                         "Every piece gets random skills and points; high values are increasingly rare.")),
            )),
            Option("armor_skill_max_count", T("Habilidades por pieza (máximo)", "Skills per piece (maximum)"),
                   T("Cada pieza recibe entre 1 y este número de habilidades (el juego admite hasta 5)."
                     " Si no estás seguro, se recomienda dejar el valor por defecto.",
                     "Each piece gets between 1 and this many skills (the game holds up to 5)."
                     " If unsure, leaving the default is recommended."),
                   minimum=1, maximum=5, requires="armor_skills"),
            Option("armor_skill_min_points", T("Puntos mínimos por habilidad", "Minimum points per skill"),
                   T("Puntos mínimos de cada habilidad positiva (0 cuenta como 1). Si no estás seguro, se recomienda dejar el valor por defecto.",
                     "Minimum points of each positive skill (0 counts as 1). If unsure, leaving the default is recommended."),
                   minimum=0, maximum=15, requires="armor_skills"),
            Option("armor_skill_max_points", T("Puntos máximos por habilidad", "Maximum points per skill"),
                   T("Puntos máximos de cada habilidad positiva (en el juego original rara vez pasan de 5)."
                     " Si no estás seguro, se recomienda dejar el valor por defecto.",
                     "Maximum points of each positive skill (in the original game they rarely exceed 5)."
                     " If unsure, leaving the default is recommended."),
                   minimum=1, maximum=20, requires="armor_skills"),
            Option("armor_skills_no_negative", T("Sin habilidades negativas", "No negative skills"),
                   T("Ninguna pieza recibe habilidades negativas. Ojo: cada punto negativo se compensa con un "
                     "punto positivo más, así que permitirlas también da más habilidades positivas.",
                     "No piece gets negative skills. Note: every negative point is compensated with one more "
                     "positive point, so allowing them also gives more positive skills."),
                   requires="armor_skills"),
            Option("armor_skills_shared_variants", T("Compartir entre Espadachín y Artillero",
                                                      "Share between Blademaster and Gunner"),
                   T("Las versiones de Espadachín y Artillero de una misma pieza reciben las mismas habilidades "
                     "nuevas.",
                     "The Blademaster and Gunner versions of a piece get the same new skills."),
                   requires="armor_skills"),
        ), T("Como mucho una habilidad negativa por pieza.", "At most one negative skill per piece.")),
    )),
    Section(T("Equipo OP", "OP equipment"), (
        Group(T("Límites del juego", "Game limits"), (
            Option("allow_op_equipment", T("Permitir equipo OP", "Allow OP equipment"),
                   T("Quita la comprobación del juego que rechaza las misiones (\"No puedes aceptar estos datos de "
                     "misión\") cuando llevas puesta una pieza con defensa de 180 o más (contando mejoras), una "
                     "resistencia de 10 o más, o un arma por encima de sus topes. Con la opción activada puedes "
                     "entrar a cualquier misión con cualquier arma y armadura, y las estadísticas de armadura "
                     "aleatorias ya no se limitan a esos valores. Necesita la actualización del juego "
                     "(00000000.app) para quitar todos los límites; sin ella solo se quitan los de ataque, "
                     "defensa y resistencias.",
                     "Removes the game's check that refuses quests (\"You can't accept this quest data\") when you "
                     "wear a piece with 180 or more defense (counting upgrades), a resistance of 10 or more, or a "
                     "weapon past its limits. With it on you can enter any quest with any weapon and armor, and "
                     "random armor stats are no longer kept under those values. It needs the game update "
                     "(00000000.app) to remove every limit; without it only the attack, defense and resistance "
                     "limits are removed.")),
        ), T("Desactivada, el randomizer mantiene la armadura por debajo de los límites para que las misiones "
             "se puedan aceptar.",
             "When off, the randomizer keeps armor under the limits so quests can be accepted.")),
    )),
    Section(T("Modelos", "Models"), (
        Group(T("Aspecto", "Looks"), (
            Option("randomize_models", T("Randomizar modelos", "Randomize models"),
                   T("Cambia el aspecto de armas y armaduras por el de otra de la misma clase o parte.",
                     "Changes the look of weapons and armor to that of another of the same class or part.")),
            Option("models_use_each_once", T("Usar cada modelo una sola vez", "Use each model only once"),
                   T("Se usan todos los modelos y ninguno se repite mientras sea posible.",
                     "Every model is used and none is repeated while possible."),
                   requires="randomize_models"),
        )),
        Group(T("Modo", "Mode"), (
            Option("model_mode", requires="randomize_models", choices=(
                Choice(ModelMode.FAMILIES, T("Por familias", "By families"),
                       T("Cada línea de armas toma los modelos de otra, en orden: el arma más básica recibe el "
                         "aspecto más básico. Cada conjunto de armadura toma el aspecto de otro conjunto.",
                         "Each weapon line takes the models of another, in order: the most basic weapon gets the "
                         "most basic look. Each armor set takes the look of another set.")),
                Choice(ModelMode.CHAOTIC, T("Caótico", "Chaotic"),
                       T("Cada pieza recibe cualquier modelo de su clase de arma o parte de armadura.",
                         "Each piece gets any model of its weapon class or armor part.")),
            )),
        )),
    )),
    Section(T("Felyne", "Felyne"), (
        Group(T("Recetas Felyne", "Felyne recipes"), (
            Option("randomize_palico_recipes", T("Randomizar recetas", "Randomize recipes"),
                   T("Cada arma y armadura Felyne pide materiales de monstruo del rango de la pieza, en el número y "
                     "la cantidad elegidos abajo, como el equipo de cazador.",
                     "Every Felyne weapon and armor piece asks for monster materials of its rank, in the number and "
                     "quantity chosen below, like hunter gear.")),
            materials_range("palico_recipe_material_count", "randomize_palico_recipes"),
            quantity_range("palico_recipe_quantity", "randomize_palico_recipes"),
        )),
        Group(T("Armas Felyne", "Felyne weapons"), (
            Option("randomize_palico_weapon_stats", T("Randomizar estadísticas de armas", "Randomize weapon stats"),
                   T("Los valores cambian en el juego y en los menús.", "Values change both in game and in the menus.")),
            stat("palico_weapon_attack", T("Ataque", "Attack"), "randomize_palico_weapon_stats",
                 T("Ataque cuerpo a cuerpo; el de bumerán cambia en la misma proporción.",
                   "Melee attack; the boomerang attack changes in the same proportion.")),
            stat("palico_weapon_affinity", T("Afinidad", "Affinity"), "randomize_palico_weapon_stats",
                 T("Probabilidad de golpe crítico. Progresivo no cambia las armas con 0 %.",
                   "Critical hit chance. Progressive leaves weapons at 0% unchanged.")),
            stat("palico_weapon_element", T("Valor del elemento", "Element value"), "randomize_palico_weapon_stats",
                 T("Valor del elemento de las armas que lo tienen.", "Element value of the weapons that have one.")),
            stat("palico_weapon_defense", T("Bonus de defensa", "Defense bonus"), "randomize_palico_weapon_stats",
                 T("Defensa extra que dan algunas armas. Progresivo no se la añade a las que no la tienen.",
                   "Extra defense some weapons give. Progressive does not add it to weapons without it.")),
            Option("palico_weapon_element_type", T("Cambiar el elemento", "Change the element"),
                   T("Las armas con elemento reciben otro distinto (fuego, agua, rayo, hielo o dragón).",
                     "Weapons with an element get a different one (fire, water, thunder, ice or dragon)."),
                   requires="randomize_palico_weapon_stats"),
            Option("palico_weapon_element_add_remove", T("Añadir y quitar elemento", "Add and remove element"),
                   T("Cualquier arma puede ganar o perder su elemento, en la misma proporción que las armas Felyne "
                     "de su rango en el juego original.",
                     "Any weapon may gain or lose its element, in the same proportion as the Felyne weapons of its "
                     "rank in the original game."),
                   requires="randomize_palico_weapon_stats"),
        ), STAT_MODES_HELP),
        Group(T("Armaduras Felyne", "Felyne armor"), (
            Option("randomize_palico_armor_stats", T("Randomizar estadísticas de armaduras",
                                                     "Randomize armor stats"),
                   T("Los valores cambian en el juego y en los menús.", "Values change both in game and in the menus.")),
            stat("palico_armor_defense", T("Defensa", "Defense"), "randomize_palico_armor_stats",
                 T("Defensa de cada casco y torso.", "Defense of each head and body piece.")),
            stat("palico_armor_resistances", T("Resistencias elementales", "Elemental resistances"),
                 "randomize_palico_armor_stats",
                 T("Resistencias a fuego, agua, rayo, hielo y dragón de cada pieza; las del conjunto son la suma "
                   "de casco y torso.",
                   "Fire, water, thunder, ice and dragon resistances of each piece; a set's are head plus body.")),
        ), STAT_MODES_HELP),
        Group(T("Aspecto Felyne", "Felyne looks"), (
            Option("randomize_palico_models", T("Randomizar modelos", "Randomize models"),
                   T("Cambia el aspecto de armas y armaduras Felyne por el de otras del mismo tipo.",
                     "Changes the look of Felyne weapons and armor to that of others of the same kind.")),
            Option("palico_model_mode", requires="randomize_palico_models", choices=(
                Choice(PalicoModelMode.FULL_SET, T("Conjunto completo", "Whole set"),
                       T("Arma, casco y torso de un tema toman juntos el aspecto de otro tema (p. ej. todo lo de "
                         "Kut-Ku pasa a verse como Rathalos).",
                         "A theme's weapon, head and body take the look of another theme together (e.g. all the "
                         "Kut-Ku gear looks like Rathalos).")),
                Choice(PalicoModelMode.SEPARATE, T("Armas y armaduras por separado", "Weapons and armor apart"),
                       T("Las armas cambian entre sí y los conjuntos de armadura (casco y torso) entre sí.",
                         "Weapons swap among themselves and armor sets (head and body) among themselves.")),
                Choice(PalicoModelMode.CHAOTIC, T("Caótico", "Chaotic"),
                       T("Cada pieza recibe cualquier modelo de su tipo.", "Each piece gets any model of its kind.")),
            )),
            Option("palico_models_use_each_once", T("Usar cada modelo una sola vez", "Use each model only once"),
                   T("Se usan todos los modelos y ninguno se repite mientras sea posible.",
                     "Every model is used and none is repeated while possible."),
                   requires="randomize_palico_models"),
        )),
    )),
)

INTERFACE_SECTIONS: tuple[Section, ...] = (
    Section(T("HUD", "HUD"), (
        Group(T("Tamaño del HUD", "HUD size"), (
            Option("hud_scale", T("Tamaño", "Size"),
                   T("Tamaño de lo que se dibuja sobre el juego en la pantalla superior.",
                     "Size of what is drawn over the game on the top screen."),
                   choices=(
                       Choice(HudScale.FULL, T("100 % (original)", "100% (original)")),
                       Choice(HudScale.P90, T("90 %", "90%")),
                       Choice(HudScale.P80, T("80 %", "80%")),
                       Choice(HudScale.P70, T("70 %", "70%")),
                       Choice(HudScale.P60, T("60 %", "60%"),
                              T("Difícil de leer en la pantalla de una 3DS.", "Hard to read on a 3DS screen.")),
                   ), compact=True),
        ), T("Pensado para jugar en un monitor. Cada elemento se encoge hacia su esquina: reloj, vida, aguante, "
             "filo y medidores del arma, lista del grupo, selector de objetos, minimapa, medidor de montar y "
             "avisos sobre los personajes. Necesita la ROM y la actualización (se busca en Citra, Azahar o "
             "Lime3DS, o se indica a la izquierda): parte del cambio va en el ejecutable de la actualización.",
             "Meant for playing on a monitor. Each element shrinks towards its corner: clock, health, stamina, "
             "sharpness and weapon gauges, party list, item selector, minimap, mount gauge and the prompts over "
             "the characters. Needs the ROM and the update (found in Citra, Azahar or Lime3DS, or set on the "
             "left): part of the change goes into the update's executable.")),
        Group(T("Objetivo", "Target"), (
            Option("target_switch", T("Cambiar de objetivo con L + ↑", "Switch the target with L + D-pad up"),
                   T("Con L pulsado (modo objetos), arriba en la cruceta fija el monstruo grande o cambia al otro, "
                     "igual que tocar el panel de la cámara de objetivo; el selector de objetos lo indica. Con L "
                     "pulsado la cruceta ya no mueve la cámara (el C-stick sí).",
                     "With L held (item mode), D-pad up locks the large monster or switches to the other one, like "
                     "a tap on the target camera panel; the item selector shows the hint. With L held the D-pad no "
                     "longer moves the camera (the C-stick still does).")),
            Option("target_face_top", T("Cara del objetivo arriba", "Target face on the top screen"),
                   T("Muestra la cara del monstruo del panel de la cámara de objetivo también en la pantalla "
                     "superior, a la izquierda del selector de objetos, con su marca de fijado.",
                     "Shows the monster face of the target camera panel on the top screen too, left of the item "
                     "selector, with its lock mark.")),
        ), T("Para jugar solo con la pantalla superior. Funcionan con el panel de la cámara de objetivo puesto en "
             "la pantalla táctil, y solo cuando el monstruo ya se ha encontrado (como el panel). Necesitan la "
             "ROM y la actualización.",
             "For playing with the top screen only. They work with the target camera panel on the touch screen, "
             "and only once the monster has been found (like the panel). They need the ROM and the update.")),
        Group(T("Iconos", "Icons"), (
            Option("new_monster_icons", T("Iconos propios, sin «?»", "Icons of their own, no \"?\""),
                   T("Ningún monstruo se muestra con el icono «?». Los Fatalis (negro, carmesí, blanco y carmesí "
                     "súper) y Gogmazios reciben un icono propio en el tablón, la cámara de objetivo y los menús, "
                     "y las misiones de Dalamadur muestran su cabeza y su cola. Las imágenes son los PNG de 36×36 "
                     "de mh4u_rando/data/icons/ y se pueden sustituir.",
                     "No monster is shown with the \"?\" icon. The Fatalis (black, crimson, white and super "
                     "crimson) and Gogmazios get an icon of their own on the quest board, the target camera and "
                     "the menus, and Dalamadur's quests show its head and its tail. The images are the 36×36 PNGs "
                     "of mh4u_rando/data/icons/ and can be replaced.")),
        ), T("Los iconos nuevos necesitan la ROM y la actualización (el atlas de iconos está en sus archivos); "
             "sin ellas se avisa y los Fatalis y Gogmazios siguen con «?».",
             "The new icons need the ROM and the update (the icon atlas is in its files); without them a warning "
             "is shown and the Fatalis and Gogmazios keep the \"?\".")),
    )),
)

AREAS: tuple[Area, ...] = (
    Area(T("Misiones", "Quests"), QUEST_SECTIONS),
    Area(T("Equipo", "Equipment"), EQUIPMENT_SECTIONS),
    Area(T("Interfaz", "Interface"), INTERFACE_SECTIONS),
)
SECTIONS: tuple[Section, ...] = QUEST_SECTIONS + EQUIPMENT_SECTIONS + INTERFACE_SECTIONS


def all_options() -> list[Option]:
    return [option for section in SECTIONS for group in section.groups for option in group.options]


def all_texts() -> list[T]:
    """Every translatable text of the option panels (for tests)."""
    texts = [area.title for area in AREAS]
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
