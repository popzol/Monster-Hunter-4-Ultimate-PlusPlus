import json

import pytest

from mh4u_rando.data import query
from mh4u_rando.data.gamedata import load_game_data


def _first_monster_id() -> int:
    return next(iter(load_game_data().monsters))


def test_monster_by_id_returns_one_record(capsys):
    monster_id = _first_monster_id()
    assert query.main(["monster", str(monster_id)]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["monster_id"] == monster_id


def test_monster_by_name_ignores_case(capsys):
    data = load_game_data()
    monster = data.monsters[_first_monster_id()]
    assert query.main(["monster", monster.name.upper()]) == 0
    ids = {json.loads(line)["monster_id"] for line in capsys.readouterr().out.strip().splitlines()}
    assert monster.monster_id in ids


def test_map_record_omits_spawn_positions(capsys):
    data = load_game_data()
    map_id = next(i for i, m in data.maps.items() if m.areas)
    assert query.main(["map", str(map_id)]) == 0
    area = next(iter(json.loads(capsys.readouterr().out)["areas"].values()))
    assert isinstance(area["large_monster_spawns"], int)


def test_equipment_lookup(capsys):
    assert query.main(["equipment", "great_sword", "1"]) == 0
    assert json.loads(capsys.readouterr().out)["id"] == 1


def test_unknown_name_fails(capsys):
    assert query.main(["item", "no-such-item-xyz"]) == 1


def test_unknown_equipment_group_fails():
    with pytest.raises(SystemExit):
        query.main(["equipment", "no_such_group"])
