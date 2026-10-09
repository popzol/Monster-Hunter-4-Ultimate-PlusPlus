# Rama `fix-mode`: notas temporales

Borrar este archivo antes de fusionar con `main`.

## Qué se ha hecho

- **Modo «Arreglar»** (GUI y CLI `--fix`): para amigos que juegan la misma semilla. Permite re-sortear una
  misión, re-sortear todas o cambiar un ajuste global sin perder el progreso, y todos obtienen el mismo mod.
  - `Settings.quest_reroll` / `quest_rerolls`: semilla efectiva por misión (`Settings.quest_seed`). Las
    misiones no re-sorteadas y el equipo no cambian.
  - `mh4u_rando/record.py`: `settings_<semilla>.json` guarda ahora un bloque `"run"` con la versión, la
    revisión, el checksum y el historial. El checksum cubre las misiones (sin los dibujos del tablón) y las
    tablas de equipo, más el código corto `XXXX-XXXX`. Las opciones personales (`PERSONAL_FIELDS`) no
    cuentan.
  - `mh4u_rando/fix.py`:
    - `preview` regenera la partida actual en memoria y la bloquea si no da su checksum (versión distinta).
      Comprueba las reglas de seguridad (no cambiar la semilla, no quitar «Equipo OP») y lista las misiones y
      el equipo que cambian.
    - `apply` hace una copia en `backups/`, escribe y verifica; si algo falla, restaura la copia.
  - `pipeline.generate()`: misiones y equipo en memoria, sin escribir nada.
  - GUI:
    - selector Randomizar/Arreglar;
    - tarjeta «Partida» (cargar el JSON o tomarlo de la carpeta);
    - área «ARREGLOS» (re-sortear una misión con buscador, todas, historial);
    - botón Previsualizar → Aplicar arreglo; cualquier edición lo devuelve a Previsualizar.
- **Plataforma Emulador / 3DS**: la de 3DS se muestra como «próximamente» y no deja randomizar.
  `Option.emulator_only` (en `touchless_target`) se desactiva en 3DS.
- Versión 0.2.0 (`mh4u_rando/__init__.py` = `pyproject.toml`, comprobado por test).
- Docs: `docs/randomizer.md` («Fixing a game in progress», «Platforms»), `docs/game_rules.md`, `README.md`,
  `docs/roadmap.md`.
- Tests:
  - `tests/test_fix.py`, que con `MH4U_ROM` incluye dos amigos con el mismo resultado byte a byte, el bloqueo
    por versión distinta y la independencia de `PYTHONHASHSEED`;
  - nuevos tests de GUI.
  - Todo pasa con la ROM.

## Segunda tanda (2026-10-09)

- Barra lateral a 740 px: no cabía (el pie de idioma/apariencia quedaba cortado: hacían falta ~845 px en
  Randomizar). Compactada (idioma y apariencia en una fila, márgenes menores) y comprobada por
  `test_sidebar_fits_the_minimum_height` (mide con `winfo_*`, sin capturas). `MIN_SIZE` en `gui/app.py`.
- Restaurar copias de `backups/`: `fix.list_backups` / `fix.restore` (guarda antes el mod actual; nunca
  poda la copia que se restaura), tarjeta «Copias de seguridad» en ARREGLOS, CLI `--list-backups` /
  `--restore NAME` (sin `--rom`).
- Vista previa con el nombre del mapa (GUI y CLI; `GameData.map_name`).
- Aviso de partidas pre-0.2.0 con el consejo de aplicar todos el mismo fichero arreglado.

## Pendiente

- **Probar en el juego**: re-sortear una misión de una partida empezada, instalar el mod y comprobar que la
  partida guardada conserva el progreso y que la misión es la nueva.
- **Modo 3DS real** (rama aparte, ya en `docs/roadmap.md`).
