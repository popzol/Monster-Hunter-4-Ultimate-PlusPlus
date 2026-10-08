Plan: elementos de "Ideas / smaller items" del roadmap
Contexto
El usuario eligió, elemento por elemento, qué ideas de docs/roadmap.md (sección Ideas / smaller items) implementar. Ninguno se marcó como "Nunca", así que no se borra nada: Arenas y DLC cifrado se quedan en el roadmap.

Se implementan estos ocho:

Investigación de música.
Interruptores para los randomizers de misiones y de equipo.
Inventario inicial editable.
Munición y revestimientos garantizados en los baúles, con los baúles ordenados.
Subobjetivos en frase natural y presentes siempre que se pueda.
Textos regenerados con artículos correctos.
Captura → Caza también en el texto.
Datos de equipo específicos de clase y bonus de set Felyne.
Reglas generales:

Código, comentarios y documentación en inglés.
La GUI es bilingüe: T(es, en) en gui/options.py.
Los hallazgos se documentan en docs/ y los temporales de investigación se borran.
Tras cada cambio de API pública se ejecuta python tools/gen_codemap.py.
Cada opción nueva se documenta en docs/randomizer.md.
1. Toggles de randomizer de misiones y de equipo (HECHO)
Ajustes (randomizer/settings.py):

Campos nuevos randomize_quests: bool = True y randomize_equipment: bool = True.
randomizes_equipment (l.209) pasa a exigir además randomize_equipment.
Se añaden a restrictions en tests/test_gui_options.py, que es la lista de bools con valor por defecto True.
GUI:

gui/options.py: un nuevo campo Area.master: str | None, con el interruptor maestro al principio del área (Quests → randomize_quests, Equipment → randomize_equipment).
gui/app.py: en _wire_requirements (l.247), cuando el maestro está apagado se desactivan todos los widgets del área.
_start (l.355) usa la propiedad ya corregida.
Pipeline (pipeline.py l.218):

Si randomize_quests es False, no se llama a randomize_quests. Aun así se aplican replace_unknown_pictures (iconos nuevos, opción de interfaz) y se escribe el ARC solo si cambió algo.
report.unrandomized_quests no debe marcar todas las misiones como "sin randomizar" en ese caso.
CLI (__main__.py): flags --no-quests y --no-equipment.

Herramientas: comprobar tools/bisect_mod.py (usa EQUIPMENT_SWITCHES).

2. Suministros: munición/revestimientos garantizados y baúl ordenado (HECHO; ensure_map va antes de la munición para que no pise un hueco)
Todo en randomizer/supplies.py.

Opción nueva gunner_supplies: bool = False, con requires="randomize_supplies".

Garantiza un mínimo de 4 stacks de munición o revestimientos en total entre todos los baúles de la misión (inicial + reabastecimiento).
Si hay menos de 4 huecos con objeto, se usan todos.
Los objetos son distintos y al azar.
Pool: data.items con category == AMMO, usable y carry_limit no nulo. Así quedan fuera Normal S Lv1 (sin límite) y el id 124 "(No Coating)".
Cantidad = carry_limit, que es el mismo criterio de stack lleno que el resto del baúl.
Los huecos se eligen al azar entre los huecos con objeto, sin contar el Mapa.
Usa un stream rng propio ("gunner_supplies") para no alterar las semillas existentes.
Orden: siempre que se randomizan los suministros, cada baúl se ordena así: Mapa primero, después por item_id ascendente y los huecos vacíos al final.

La ordenación se hace después de ensure_map, en quest_randomizer.py l.197-199.
Tests:

Ajustar test_supplies_keep_slots_and_use_full_stacks.
Añadir tests de la garantía de ≥4 en total y del orden.
3. Textos de misión (objetivo, fallo, artículos, captura → caza)
Estado: HECHO (commit 1b78c36, en main). Detalle, desviaciones y límites en docs/plan_textos.md ("Estado de la implementación"); reglas en docs/game_rules.md ("Quest text"); tablas en docs/data.md.
Se basan en los textos retail, extraídos de las 301 misiones originales con tests/conftest.original_quest_files() + load_mib.

Tabla de gramática data/curated/monster_grammar.json:

Por monstruo y por idioma, el género (m/f/n) y las formas especiales:
en: a/an.
fr: elisión l'.
it: lo/uno/l'.
La forma de artículo que usa el objetivo retail ("Abate al Kushala", "Tuer le X").
La genera un script nuevo, tools/build_monster_grammar.py, que recoge los artículos de los textos de cada idioma: objetivos, descripciones y subobjetivos ("Caza una Rathian", "Erjage eine", "Caccia uno Zamtrios", "del/de la").
Los monstruos sin aparición retail se completan a mano con "verified": false, igual que monster_names.json.
Se carga en data/gamedata.py (MonsterInfo) y se documenta en docs/data.md.
Partes (curated/part_names.json):

Se añaden el género y el número de cada parte para fr e it ("la corne", "il corno", "le ali").
También se recogen de los subobjetivos retail.
TextMode.LIST_MONSTERS se redefine como "Regenerar"; el valor se mantiene para que los presets sigan valiendo.

El objetivo principal se genera desde quest.objectives reales, con el formato exacto retail por idioma (plantillas extraídas de las misiones originales):
1 objetivo: "Caza un X" / "Caza una X". Con cantidad mayor que 1: "Caza 2 Khezu".
2 especies: "Caza una Rathian\ny un Gravios".
Más de 2 especies distintas: el texto retail exacto "Caza a todos los monstruos\ngrandes".
Verbo Caza o Abate según el tipo de misión; captura siempre → caza.
Alemán con "." final. Saltos de línea \n como en el juego original.
Coherencia del objetivo: hoy apply_main_objectives corta a 2 objetivos.
Con más de 2 especies se codifica como las misiones retail de "Caza a todos". Antes hay que comprobar en las retail qué quest_type y qué objetivos usan.
Así el texto dice la verdad.
Condición de fallo: si es exactamente el texto retail de captura ("…o el objetivo muere") y la misión ya no es de captura, se pone el texto retail normal de ese idioma.
Título y descripción: se sustituyen los nombres ajustando el artículo (siguiente punto).
Se elimina el prefijo "Objetivos: A, B, C" de la descripción, porque no existe en el juego.
Artículos en replace_monster_names (en los modos REPLACE_NAMES y Regenerar):

Al cambiar un nombre se convierte el artículo o contracción que lo precede según el género del monstruo viejo y el del nuevo:
es: un/una, el/la, al/a la, del/de la.
fr: le/la/l', un/une, du/de la/de l', au/à la/à l'.
it: il/lo/la/l', un/uno/una/un', del/dello/della/dell', al…
en: a/an.
de: der/die/das, ein/eine/einen…
En alemán el caso es ambiguo de femenino a masculino. Se usa una heurística por preposición o verbo, y la limitación queda documentada en docs/game_rules.md.
Captura → caza en el modo REPLACE_NAMES: si apply_main_objectives convirtió una captura en caza, se regeneran el objetivo y el fallo con el generador anterior, aunque el modo sea solo reemplazar nombres. KEEP no toca nada.

Roadmap:

El elemento de Next "Quest monster list in text" se actualiza: el objetivo queda hecho; título y descripción quedan pendientes.
Se quitan "Replacing names keeps the original articles" y "Capture quests…".
4. Subobjetivos naturales y siempre que sea posible
Estado: HECHO (commit 1b78c36, en main). Solo se activa sub_quest: three_objectives no lo lleva ninguna misión retail con subobjetivo. El verbo romper/herir es fijo por parte. Pendiente de probar en juego (docs/roadmap.md, "To verify in-game").
Texto (text.set_sub_quest_text): plantillas retail de rotura con gramática:

en: "Break X's horn".
fr: "Briser la corne X".
es: "Rompe cuerno del/de la X".
de: "X-Horn brechen", con un compuesto con guiones como "Dah'ren-Mohran-Horn"; la parte se escribe con mayúscula.
it: "Spezza il corno del/dello/della X".
Siempre que sea posible: con SubQuestMode.RANDOMIZE, las misiones de monstruos grandes que no tenían subobjetivo también reciben uno si hay alguna parte rompible.

Se activan los flags sub_quest y three_objectives. Antes hay que comprobar en mib_format.md y en las misiones retail qué exige el juego.
Se fija reward_sub / hrp_sub con la proporción mediana retail entre recompensa sub y principal por rango. La proporción se calcula una vez y se guarda en data/tuning.py.
El cambio va en quest_randomizer.py l.182, que hoy exige has_sub_quest.
Queda en "To verify in-game": misión con subobjetivo añadido, que se pueda completar y que pague.
5. Inventario inicial editable
Ya sabemos: tabla en code.bin, offset de fichero 0xED07B8.

3 cargas de 32 ranuras (u16 item, u16 qty) cada 0x80 bytes. Es igual en el juego base y en la update.
Las referencias a 0xFD0798 están en las VA 0xC1D608 y 0xC1F75C.
Investigación:

Descompilar con Ghidra headless (tools/ghidra/Decompile.java, ver docs/hud_code.md) para saber cuándo se usa cada carga: tipo de arma/creación de personaje, petate o caja.
Comprobar también si las ranuras 24-31 son de munición.
Documentarlo en docs/game_files.md o docs/equipment_data.md.
Ajuste starting_items: list[[item_id, qty]]:

Vacío = original.
Se escribe la lista del usuario en la(s) carga(s) que use una partida nueva, siguiendo lo que salga de la investigación.
Validación:
Objetos usable.
qty ≤ carry_limit (o 99).
Máximo de ranuras.
La munición va a las ranuras de munición si así lo exige el juego.
Parche mh4u_rando/exefs/starting_items.py patch_starting_items(code, items):

Comprueba primero los 0x180 bytes originales, con el patrón de hud/icons.py:127 patch_monster_icons.
Se encadena en pipeline.py l.244-257.
La carga de code (l.207-214) también se activa con esta opción.
GUI:

Nueva opción con widget "lista de objetos": filas con un combobox de objeto filtrable más la cantidad, y botones añadir/quitar/subir/bajar.
Va en una sección "Partida nueva / New game".
Option admite un kind="items" y tests/test_gui_options.py / test_gui_app.py cubren el widget.
CLI: se configura vía --preset.

6. Investigación de música (HECHO: docs/music.md; tools/music_inventory.py, tools/music_probe.py, tools/ghidra/Strings.java; own_music corregido para Khezu, Red Khezu y Desert Seltas; shuffle y música en mapas silenciosos quedan en el roadmap)
Se busca:

El formato .mca (MADP) de sound/bgm/**: cabecera, loop start/end y códec.
Las secuencias .stq (bgm_st_NN.stq, bgm_bat.stq, str_mNN.stq).
Qué pista suena según mapa, zona o monstruo con tema propio (own_music), y las reglas de prioridad.
Se hace con un script de lectura vía exefs/romfs.py RomFS.walk() y con Ghidra (lectores de las rutas bgm_*).

Resultado:

docs/music.md con dónde están las pistas, cómo hacen loop, si se pueden reemplazar o añadir (cambiar un .mca por otro en romfs/ del mod) y la prioridad.
Prueba manual sugerida en "To verify in-game": cambiar un .mca y escucharlo.
La idea "Music research" sale del roadmap y entra lo que se descubra que es viable, por ejemplo un shuffle de música.
7. Datos de equipo específicos de clase y bonus de set Felyne
Investigación: hoy no hay nada decodificado. Pistas:

docs/equipment_data.md l.84: bytes 0x15-0x16 del arma cuerpo a cuerpo.
l.103: bytes libres del registro a distancia, 0x00-01, 0x05-07 y 0x16-0x27.
l.241: bytes 0x05/0x07/0x09 de la armadura Felyne.
records.py:152 el u16 final de la mejora de la glaive insecto.
Método:

Herramienta tools/equipment_tables.py --raw que vuelca los bytes no decodificados junto al nombre de cada arma.
Se correlacionan con los valores conocidos de Kiranico: frasco, tipo y nivel de proyectil, notas, nivel de kinsecto, cargas y revestimientos de arco, munición de ballesta, bonus de set Felyne.
Ghidra Xrefs sobre las VA de las tablas (por ejemplo 0xF77738, 0xF7B3F8, 0xF7E00C) para seguir a quien lee esos bytes. Si son índices a otra tabla (por ejemplo munición), se localiza y se añade a layout.py, tables.py (_regions, recalculando EXPECTED_TABLES_SHA256) y records.py.
Todo queda en docs/equipment_data.md.
Randomizado (módulo nuevo randomizer/equipment/specials.py, stream propio "weapon_specials"):

Opción randomize_weapon_specials (añadida a EQUIPMENT_SWITCHES) con subopciones por clase:
Frascos (hacha espada / hacha cargada).
Proyectiles (tipo y nivel).
Notas.
Kinsecto.
Cargas y revestimientos de arco.
Munición de ballesta.
Reglas, igual que el elemento:
Las mejoras conservan el tipo con weapon_upgrades_keep_element (natural_evolution).
Los niveles no bajan con weapon_upgrades_improve (_monotonic).
Bonus de set Felyne: va en palico.py con un substream nuevo, y cabeza y cuerpo del mismo set reciben el mismo bonus.
Los cambios aparecen en el spoiler con formateadores legibles (randomizer/equipment/report.py).
Las opciones finales se ajustan a lo que realmente se decodifique. Si algún campo no se encuentra, se documenta y queda en el roadmap.
Orden de trabajo
Toggles.
Suministros.
Gramática y textos (3 + 4).
Inventario inicial.
Música.
Equipo por clase. Es la investigación más larga y la más incierta.
Antes de tocar ficheros compartidos se revisa git status/log, porque hay otros agentes trabajando.

Roadmap al final:

Se quitan de Ideas los elementos hechos.
Lo pendiente de probar pasa a To verify in-game: subobjetivos añadidos, inventario inicial, munición, artículos por idioma y datos por clase.
Se conservan Arenas y DLC.
Verificación
python -m pytest, incluidos los tests nuevos:
Garantía de munición y orden del baúl.
Textos generados igual a los retail cuando el monstruo y el objetivo coinciden con los originales: con el modo Regenerar sobre una misión sin cambios, el objetivo debe ser idéntico al retail en los 5 idiomas.
Artículos tras reemplazar.
Subobjetivo añadido con flags y recompensa.
Parche de inventario con comprobación de bytes.
Toggles (pipeline sin misiones o sin equipo).
test_gui_options / test_gui_app con las opciones nuevas.
Round-trip de las tablas de equipo nuevas.
python tools/gen_codemap.py y test_codemap.
Ejecución completa por la CLI con todas las opciones contra la ROM, y revisión del spoiler.
Pruebas en juego (Citra/Azahar) para el usuario, apuntadas en el roadmap:
Partida nueva con el inventario editado.
Misión con subobjetivo añadido.
Baúl con munición.
Textos en ES/EN.
Armas con frascos o proyectiles cambiados.