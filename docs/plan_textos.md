# Plan: textos de misión (punto 3) y subobjetivos naturales (punto 4)

Expansión de los puntos 3 y 4 de `docs/implementar.md` (que sigue en `main`, sin
versionar). Rama local `quest-text-grammar`, worktree en
`C:\Users\USUARIO\Desktop\mh4u_modding\RAMAS\quest-text-grammar`.

**Ramas locales:** se crean siempre como worktree dentro de
`C:\Users\USUARIO\Desktop\mh4u_modding\RAMAS\<nombre-rama>`
(`git worktree add -b <rama> /home/USUARIO/Desktop/mh4u_modding/RAMAS/<rama> main`
con el git de devkitPro). El repo principal se queda en `main`.

**Tests en el worktree:** los volcados no están en la rama. Antes de `pytest`:
`$env:MH4U_QUEST_DIR = "C:\Users\USUARIO\Desktop\Spopzols_MH4U_Randomizer\Scripts\og_loc\loc\quest"`
(ver `tests/conftest.py`; el resto de rutas de volcados se apuntan igual si hace falta).

Reglas generales de `implementar.md`: código y docs en inglés, GUI bilingüe con
`T(es, en)`, hallazgos en `docs/`, `python tools/gen_codemap.py` tras cambiar API
pública, opciones nuevas documentadas en `docs/randomizer.md`, revisar
`git status/log` antes de tocar ficheros compartidos.

---

## 0. Hallazgos ya medidos en las 301 misiones retail

Medido con un script de lectura (borrado) sobre `original_quest_files()`. Corrigen
o precisan el plan original:

| Hallazgo | Consecuencia |
|---|---|
| **Francés no usa artículo indefinido en objetivos, usa "1"**: "Chasser 1 Rathian\net 1 Gravios", "Capturer 1 Gypceros". Con Abate y 2 objetivos repite el verbo: "Tuer 1 Seltas\nTuer 1 Reine Seltas". | Las plantillas fr del objetivo no necesitan género; el género fr solo hace falta para título/descripción y subobjetivo. |
| **Alemán objetivo en acusativo y con "."**: "Fange einen Gypceros.", "Erjage eine Rathian\nund einen Gravios.", "Erlege den Dalamadur." | Plantillas de: `einen/eine/ein` + `.` final. |
| **Algunos monstruos usan artículo definido en el objetivo** (dragones ancianos): "Slay Dalamadur", "Tuer le Dalamadur", "Abate al Dalamadur", "Erlege den Dalamadur."; pero it "Caccia un Dalamadur" (incoherencia retail). | Campo por monstruo e idioma `objective_article: "indefinite" \| "definite" \| "none"`, extraído del retail. |
| **Más de 2 especies:** `quest_type` 8 (HUNT_ALL), `objective_amount = 1`, objetivo = monstruo de la última oleada; texto "Hunt all large monsters" / "Chasser tous les grands\nmonstres" / "Caza a todos los monstruos\ngrandes" / "Erjage alle großen Monster." / "Caccia tutti i mostri grandi". También existe HUNT_ALL con 2 objetivos (m10312: "Hunt a Rathian\nand a Gravios"). | Confirma la codificación "Caza a todos". Los textos exactos se copian del retail (con sus `\n`). |
| **Fallo:** 4 variantes por idioma: normal ("Reward hits 0, or time\nexpires.", 221), sin tiempo ("Reward hits 0.", 20), captura ("…or capture target slain.", 13) y vacío (26). En de hay variantes menores (217 vs 221). | Captura → se sustituye por la variante normal del mismo idioma. Solo se toca si el texto es exactamente el de captura. |
| **Subobjetivos BREAK_PART usan dos verbos** según la parte: "Break the Seltas's horn" / "Wound the Great Jaggi's head" (fr Briser/Blesser, es Rompe/Hiere, de brechen·zerbrechen/verletzen, it Spezza/Ferisci). | El verbo depende de la parte: campo `verb: "break" \| "wound"` en `part_names.json`, recogido del retail. |
| **El retail recorta para que quepa:** quita el artículo de la parte ("Blesser oreilles Kecha Wacha", "Spezza artiglio del Kecha Wacha", "Rompe garras del K. Wacha") y abrevia nombres en es ("K. Wacha"). | Cadena de recortes por longitud (ver 4.2). Nombre corto por monstruo e idioma. |
| **Alemán usa formas de compuesto propias:** "Großjaggi-Kopf verletzen", "Kecha-Wacha-Ohren verletzen", "Das Gypceros-Projekt". | Campo `de_compound` por monstruo (por defecto: nombre con espacios → guiones). |
| **Longitud máxima de línea** (title/objetivo/sub): en 31/30/32, fr 30/32/33, es 27/31/32, de 31/34/31, it 29/31/33. **El subobjetivo nunca lleva `\n`.** | Límite por idioma y ranura guardado en la tabla; los tests comprueban que todo texto generado cabe. |
| **Ninguna misión retail con subobjetivo tiene `three_objectives`** (223 con `sub_quest`, 0 con `three_objectives`). | Al añadir un subobjetivo se activa **solo** `sub_quest`. `three_objectives` se queda como está (el plan original decía activar ambos: corregido). |
| Sin subobjetivo: 55 misiones con texto "None"/"Ninguno" en la ranura 6 y `reward_sub = hrp_sub = 0`; 26 con todas las ranuras vacías. | Solo se añaden subobjetivos a misiones con la ranura 6 no vacía. |
| Proporción mediana `reward_sub / reward_main` por rango 1–10: 0.167, 0.167, 0.148, 0.211, 0.167, 0.132, 0.117, 0.278, 0.203, 0.139. `hrp_sub / hrp` ≈ 0.10 (moda). | Van a `curated/tuning.json` (no a `tuning.py`, que solo carga el JSON). |

---

## 3. Textos de misión

### 3.1 Herramienta `tools/build_monster_grammar.py`

Entrada: las 301 misiones (`tests/conftest.original_quest_files()` + `load_mib`),
`monster_names.json` (nombres + alias) y `generated/monsters.json` (partes).

1. Para cada texto (título, objetivo, fallo, descripción, subobjetivo) y cada
   idioma, localiza cada nombre de monstruo (misma regex "más largo primero" que
   `replace_monster_names`) y la palabra o contracción que lo precede.
2. Clasifica ese token con tablas por idioma:
   * es: `un/el/al/del` → m, `una/la/a la/de la` → f.
   * fr: `le/du/au/un` → m, `la/de la/à la/une` → f, `l'/de l'/à l'` → elisión (sin género).
   * it: `il/lo/un/uno/del/dello/al/allo` → m, `la/una/della/alla` → f, `l'/un'/dell'/all'` → elisión;
     `lo/uno/dello` marca además "forma lo".
   * de: `der/den/dem/des/ein/einen/einem/eines` → m, `die/eine/einer` → f, `das/ein` (neutro, ambiguo con m) → n si aparece `das`.
   * en: `a` / `an`.
3. Vota por monstruo y lengua; si hay votos en conflicto, gana la mayoría y se
   imprime un aviso para revisar a mano.
4. Del objetivo principal retail saca `objective_article` (indefinido, definido o ninguno).
5. De subobjetivos y títulos saca `de_compound` ("Großjaggi") y los nombres cortos
   ("K. Wacha"; los alias de `monster_names.json` ya tienen parte de esto).
6. Del subobjetivo BREAK_PART saca por parte (inglés de `monsters.json`):
   verbo (break/wound) y, en fr/it/es, el artículo de la parte → género y número.
7. Mide la longitud máxima de línea por idioma y ranura.
8. Escribe `data/curated/monster_grammar.json` **conservando las entradas
   `verified: false` escritas a mano** (mismo patrón que `monster_names.json`) y
   añade/actualiza los campos de partes en `part_names.json` sin pisar lo manual.
9. Con `--ratios` imprime las medianas de recompensa sub/principal por rango
   (para `tuning.json`, punto 4).

### 3.2 Datos

`data/curated/monster_grammar.json`:

```json
{
  "description": "...",
  "max_line": {"en": {"title": 31, "objective": 30, "sub": 32}, "...": {}},
  "monsters": {
    "1": {
      "en": {"article": "a"},
      "fr": {"gender": "f"},
      "es": {"gender": "f"},
      "de": {"gender": "f", "compound": "Rathian"},
      "it": {"gender": "f"},
      "objective_article": {"en": "indefinite", "fr": "indefinite", "es": "indefinite", "de": "indefinite", "it": "indefinite"},
      "short": {"es": "Rathian"},
      "verified": true
    }
  }
}
```

* Elisión fr/it y formas "lo/uno" en it: se **calculan** del nombre (vocal, h
  muda, `z`, `s`+consonante, `gn`, `ps`, `x`, `y`) y el campo `elision`/`lo_form`
  solo se escribe para excepciones.
* Monstruos sin aparición retail (los de G-rank sin misión propia, variantes
  apex, etc.): se rellenan a mano con `"verified": false`.
* `part_names.json`: cada parte gana `"verb": "break"|"wound"` y, por idioma,
  `{"name": "corne", "gender": "f", "plural": false}` (fr, it, es). El formato
  plano actual (`"fr": "bras"`) se migra; `GameData.part_name()` sigue devolviendo
  el nombre.
* Se carga en `data/gamedata.py`: `MonsterInfo.grammar: dict[str, MonsterGrammar]`
  (dataclass `gender`, `article`, `compound`, `short`, `objective_article`) y
  `GameData.part_grammar(part, lang)`. Se documenta en `docs/data.md` (esquema +
  cómo regenerar).
* Test en `test_gamedata.py`: todo monstruo de `large_monsters()` tiene gramática
  completa en los 5 idiomas y toda parte rompible tiene verbo y género.

### 3.3 Módulo nuevo `randomizer/grammar.py`

Funciones puras, sin `Quest`, para poder probarlas por separado:

* `article(lang, kind, gender, name, case="acc")` → `"una"`, `"l'"`, `"dello"`, `"einen"`…
  `kind ∈ {indefinite, definite, de, a}` (contracciones es/fr/it).
* `noun_phrase(monster, lang, kind)` → `"una Rathian"`, `"l'Akantor"`, `"dello Zamtrios"`.
* `convert_article(token, lang, old_grammar, new_grammar, new_name)` → el
  token equivalente para el monstruo nuevo, o `None` si no es un artículo
  conocido (entonces no se toca).
* `de_compound(monster)` y `fit(candidates, limit)` (primera variante que cabe).

### 3.4 `TextMode.LIST_MONSTERS` → "Regenerar"

* El valor `"list_monsters"` se mantiene (presets); el miembro se renombra a
  `TextMode.REGENERATE = "list_monsters"` con alias `LIST_MONSTERS` para no romper
  código/tests, o se deja el nombre y solo cambia la etiqueta (decisión técnica:
  renombrar con alias).
* GUI (`gui/options.py:216`): `T("Regenerar", "Regenerate")` y tooltip nuevo.
* `docs/randomizer.md:29`: nueva descripción.
* Comportamiento: título y descripción como REPLACE_NAMES (con artículos);
  objetivo y fallo generados; subobjetivo según `sub_quests`.

### 3.5 Generador del objetivo principal (`text.write_main_objective`)

Fuente: `quest.objectives[:objective_amount]` y `quest.quest_type` reales (no el
plan), así el texto siempre dice lo que el juego comprueba. Solo se genera si
`objectives.main_objectives_target_large_monsters(quest)`; si no (entregas,
pequeños), no se toca.

Plantillas por idioma (en `text.py`), verbo según `ObjectiveType`/`quest_type`:

| | Hunt | Slay | 2 especies | Todos |
|---|---|---|---|---|
| en | Hunt {np} | Slay {np} | {verb} {np1}\nand {np2} | Hunt all large monsters |
| fr | Chasser {n} {name} | Tuer {n} {name} | Chasser 1 A\net 1 B · Tuer 1 A\nTuer 1 B | Chasser tous les grands\nmonstres |
| es | Caza {np} | Abate {np} | Caza una A\ny un B | Caza a todos los monstruos\ngrandes |
| de | Erjage {np}. | Erlege {np}. | Erjage eine A\nund einen B. | Erjage alle großen Monster. |
| it | Caccia {np} | Uccidi {np} | Caccia una A\ne un B | Caccia tutti i mostri grandi |

* `{np}` usa `objective_article` del monstruo (indef/def/ninguno). Cantidad > 1:
  "Caza 2 Khezu", "Hunt 2 Khezu" (confirmar forma exacta con el retail en el test
  y ajustar).
* Verbo de "Todos" en Slay: comprobar si existe retail SLAY_ALL con texto propio;
  si no, se usa el de Hunt.
* Captura siempre → caza (el verbo Capture no se genera nunca).
* Los textos "Todos" se copian literales del retail con sus `\n`.
* Si la línea pasa de `max_line`, se parte por el conector (`\nand`) como el retail.

**Coherencia del objetivo** (`objectives.apply_main_objectives`):

* Hoy corta a 2 objetivos sin cambiar el tipo. Nuevo: si hay > 2 especies
  objetivo, `quest_type` pasa a `*_ALL` (`_SINGLE_TO_ALL`), `objective_amount = 1`
  y el objetivo apunta a la última especie de la última oleada (patrón retail
  m10419). El enum ya documenta que `HUNT_ALL` exige cazar todos los grandes.
* `apply_main_objectives` devuelve `bool` "convertí una captura en caza" (o lo
  guarda en `QuestReport.capture_to_hunt`), que usa 3.7.

**Condición de fallo** (`text.fix_failure_text`): si la ranura 2 es exactamente
la variante "captura" del idioma y `quest_type`/objetivos ya no son de captura,
se pone la variante normal del mismo idioma. Las variantes se guardan como
constantes literales copiadas del retail.

**Descripción:** se elimina el prefijo "Objetivos: A, B, C" (y `TARGETS`). El
punto del roadmap "Quest monster list in text" queda pendiente para título y
descripción.

### 3.6 Artículos al reemplazar nombres (`replace_monster_names`)

* La regex actual (nombres, más largo primero) se amplía con un grupo opcional
  que captura el artículo/contracción anterior por idioma:
  es `(?:\b(un|una|el|la|al|a la|del|de la)\s+)?`, fr `(le |la |l'|du |de la |de l'|au |à la |à l'|un |une )?`,
  it `(il |lo |la |l'|un |uno |una |un'|del |dello |della |dell'|al |allo |alla |all'|dal…|nel…|sul…)?`,
  de `(der|die|das|den|dem|des|ein|eine|einen|einem|einer|eines) `, en `(a|an) `.
  Se respetan mayúsculas iniciales ("La", "Le", "Der").
* Si el monstruo viejo y el nuevo difieren en género/forma, `grammar.convert_article`
  da el nuevo token; si no, se deja igual.
* Alemán: compuestos (`Name-…` o `…-Name`) no cambian artículo (el artículo es del
  núcleo). Caso ambiguo (f→m: `die`/`eine` puede ser nom. o ac.; `der` f puede ser
  dat./gen.): heurística por la palabra anterior —preposiciones de dativo
  (`mit, von, bei, zu, aus, nach, gegenüber`), de acusativo (`für, gegen, durch, um, ohne`),
  verbo imperativo de objetivo → acusativo; por defecto nominativo en títulos y
  acusativo en objetivos. Limitación documentada en `docs/game_rules.md`
  (sección "Quest text").
* No se tratan adjetivos entre artículo y nombre ("einen wütenden Rathalos"):
  limitación documentada.
* Se aplica en REPLACE_NAMES y Regenerar (título, descripción y, en REPLACE,
  objetivo y subobjetivo). También en `_repair_objectives`
  (`quest_randomizer.py:220`), que hoy solo reemplaza en REPLACE_NAMES; en
  Regenerar, tras reparar, se vuelve a generar el objetivo.

### 3.7 Captura → caza en REPLACE_NAMES

En `quest_randomizer.py` (tras `apply_text`, l.~186): si `apply_main_objectives`
convirtió una captura en caza, se regeneran objetivo (3.5) y fallo (3.5) aunque el
modo sea REPLACE_NAMES. KEEP no toca nada. Ojo: hoy la conversión solo ocurre si
cambia la alineación (`_wave_ids(quest) != original_lineup`); se mantiene así.

### 3.8 Tests (punto 3)

* `test_text_regenerate_matches_retail` (necesita volcados): para cada misión
  retail con objetivos sobre grandes, regenerar sobre la misión **sin cambios** da
  el objetivo idéntico al retail en los 5 idiomas. Lista explícita de excepciones
  retail con motivo (p. ej. it "Caccia un Dalamadur" en una de Abate, misiones de
  captura cuyo texto cambia a propósito).
* `test_failure_text_capture_replaced`.
* `test_replace_names_articles`: casos fijos por idioma
  (es "Caza una Rathian" → "Caza un Tigrex", "de la Rathian" → "del Tigrex";
  fr "la Rathian" → "le Tigrex", → "l'Akantor"; it "il Rathalos" → "lo Zinogre";
  de "eine Rathian" → "einen Tigrex"; en "a Rathian" → "an Akantor").
* `test_grammar_*`: funciones puras de `grammar.py`.
* `test_more_than_two_species_is_hunt_all` en `test_randomizer.py`.
* Ajustar `test_randomizer.py:42` y `:227` (usan LIST_MONSTERS y el prefijo "Targets").
* Longitudes: todo objetivo generado ≤ `max_line` (o documentado).

---

## 4. Subobjetivos naturales y siempre que se pueda

### 4.1 Plantillas (`text.set_sub_quest_text`)

Formato retail, verbo según `part.verb`:

| | break | wound |
|---|---|---|
| en | Break the {M}'s {part} | Wound the {M}'s {part} |
| fr | Briser {art}{part} {M} | Blesser {art}{part} {M} |
| es | Rompe {art}{part} {de}{M} | Hiere {art}{part} {de}{M} |
| de | {Compound}-{Part} brechen | {Compound}-{Part} verletzen |
| it | Spezza {art}{part} {di}{M} | Ferisci {art}{part} {di}{M} |

* en: "the" según `objective_article` (definido → sin "the": "Break Nerscylla's…"
  sale en el retail; se extrae por monstruo). Posesivo `'s` siempre (retail
  "Seltas's").
* fr: artículo de la parte (`la `, `le `, `l'`, `les `), sin "de" ante el monstruo.
* es: artículo de la parte + `del`/`de la` según el monstruo.
* de: compuesto con guiones; la parte con mayúscula; "brechen" por defecto
  ("zerbrechen" aparece en alguna: se respeta si el retail lo usa para esa parte).
* it: artículo de la parte + `del/dello/della/dell'/degli` según el monstruo.

### 4.2 Recortes por longitud (`grammar.fit`, límite `max_line[lang]["sub"]`)

1. Frase completa.
2. Sin artículo de la parte (fr/es/it, como el retail).
3. Nombre corto del monstruo (`short`, p. ej. "K. Wacha").
4. Si aún no cabe: se acepta y el test lo lista (se revisará en juego).

Test: para todo monstruo × parte rompible, en los 5 idiomas, la frase cabe; la
lista de excepciones es explícita y documentada.

### 4.3 Añadir subobjetivo cuando no había (`SubQuestMode.RANDOMIZE`)

* `quest_randomizer.py:182`: la condición pasa a
  `has_sub_quest(quest) or (settings.sub_quests is RANDOMIZE and can_add_sub_quest(quest))`.
* `objectives.can_add_sub_quest(quest)`: `main_objectives_target_large_monsters`,
  ranura 6 de texto no vacía en algún idioma (excluye las 26 misiones sin textos),
  no es misión de llegada/entrega.
* `objectives.add_sub_quest(quest, plan, data, rng)`: reutiliza
  `randomize_sub_quest`; si devuelve objetivo, activa **solo** `sub_quest` y fija
  `reward_sub = round(reward_main × ratio[rank], -1)` y
  `hrp_sub = round(hrp × hrp_ratio[rank])` (0 si `hrp` es 0). Si no hay partes
  rompibles, la misión se queda sin subobjetivo (no se llama a `disable_sub_quest`
  para no tocar recompensas originales).
* Antes de codificar: revisar en `docs/mib_format.md` y en el retail el byte de
  `three_objectives` (puede tener otro sentido) y si alguna misión retail activa
  `sub_quest` con `objective_sub` vacío. Lo que salga va a `docs/mib_format.md`.
* `curated/tuning.json`, sección `quests`: `sub_reward_ratio` `{"1": 0.167, …}` y
  `sub_hrp_ratio`, con descripción "mediana retail por rango, `tools/build_monster_grammar.py --ratios`".
* El stream rng es el ya existente `"sub_quest"`; las semillas de misiones que ya
  tenían subobjetivo no cambian.
* `QuestReport.sub_quest_added: bool` y línea en el spoiler (`report.py:64`).
* `_repair_objectives` no cambia: un subobjetivo añadido apunta a un monstruo del
  plan.

### 4.4 Tests (punto 4)

* `test_sub_quest_text_matches_retail`: con monstruo y parte originales, la frase
  generada es idéntica al retail (con lista de excepciones).
* `test_sub_quest_added`: misión sin subobjetivo + RANDOMIZE → `sub_quest` activo,
  `three_objectives` intacto, objetivo BREAK_PART válido, `reward_sub > 0`,
  texto ≠ "None" en los 5 idiomas, round-trip MIB correcto.
* `test_sub_quest_text_is_translated` (existe, `test_randomizer.py:163`): adaptar.
* KEEP no añade nada; DISABLE sigue igual.

---

## Documentación y roadmap

* `docs/data.md`: `monster_grammar.json`, nuevos campos de `part_names.json`,
  `tools/build_monster_grammar.py`.
* `docs/game_rules.md`: sección "Quest text" (plantillas retail, artículo definido
  de dragones ancianos, recortes por longitud, limitación del alemán), y en
  "Objectives" la regla de > 2 especies y la de añadir subobjetivo (solo `sub_quest`).
* `docs/mib_format.md`: lo que se averigüe de `three_objectives`.
* `docs/randomizer.md`: `text` (Regenerar) y `sub_quests` (RANDOMIZE añade).
* `docs/roadmap.md`: "Quest monster list in text" → objetivo hecho, título y
  descripción pendientes; quitar "Sub quest text is…", "Replacing names keeps the
  original articles" y "Capture quests become Hunt…". Añadir a "To verify
  in-game": misión con subobjetivo añadido (se completa y paga), textos ES/EN/DE.
* `python tools/gen_codemap.py` al final.

## Orden de trabajo (commits pequeños en la rama)

1. `build_monster_grammar.py` + `monster_grammar.json` + `part_names.json` migrado
   + carga en `gamedata.py` + tests de datos. Revisión manual de avisos y
   rellenado `verified: false`.
2. `grammar.py` + tests unitarios.
3. Generador de objetivo y fallo + coherencia > 2 especies + modo Regenerar +
   test contra retail.
4. Artículos en `replace_monster_names` + captura → caza en REPLACE_NAMES.
5. Plantillas de subobjetivo + recortes + test contra retail.
6. Añadir subobjetivos (+ tuning, report, spoiler).
7. GUI/docs/roadmap/codemap; `python -m pytest` completo; ejecución CLI con
   `--preset` de todo activado y revisión del spoiler y de algunos textos.

## Riesgos

* Excepciones retail (incoherencias de traducción) harán fallar el test "idéntico
  al retail": se listan explícitamente, no se fuerzan en el generador.
* Alemán: casos con adjetivos o caso ambiguo quedarán mal en algunos títulos.
* Subobjetivo añadido: si el juego exigiera algo más que el flag (p. ej. una
  tabla de recompensas sub), se notaría solo en juego → "To verify in-game".

---

## Estado de la implementación (rama `quest-text-grammar`)

Hecho: pasos 1–7 del plan, con estas diferencias respecto a lo previsto (medidas en las misiones retail):

* **Verbo del objetivo:** sigue el `quest_type` (Slay/Hunt/Capture), no el tipo del objetivo.
* **fr:** la segunda línea repite el verbo ("Chasser 1 A\nChasser 1 B"; 30 de 36 misiones retail).
* **"Hunt all large monsters":** solo con tipo `*_ALL`, un objetivo y más de una especie.
* **Subobjetivo:** el verbo (break/wound) es fijo por parte, porque el retail lo alterna de misión a misión;
  por eso el test del subobjetivo comprueba plantillas fijas y que cabe en la línea, no igualdad con el retail.
* **Alemán:** nombres que empiezan con adjetivo ("Roter Khezu") se declinan tras el artículo; también se
  reconocen sus formas declinadas al reemplazar nombres.
* **Nombres partidos por salto de línea** ("Kushala\nDaora") ahora también se reemplazan.
* Los volcados (`Scripts`, `Documentation`, `Input`) del worktree son *junctions* al repo principal (ignorados
  por git). No usar `Remove-Item -Recurse` sobre ellos; quitar con `rmdir` sin `/s`.
* No se activa `three_objectives` (ninguna misión retail lo usa).
