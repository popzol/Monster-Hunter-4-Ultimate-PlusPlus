"""Semi-fake progress bar of the GUI (pure logic, no window)."""

from mh4u_rando.gui.progress import CHECKPOINTS, MIN_STAGE_SECONDS, ProgressAnimator


def test_progress_animation_reaches_every_checkpoint_in_order():
    now = 0.0
    bar = ProgressAnimator(now)
    for name in ("rom", "quests", "write", "done"):  # all reported at once: a very fast run
        bar.push_stage(name)
    values, stages = [], []
    while not bar.finished:
        now += 0.03
        values.append(bar.tick(now))
        stages.append(bar.stage)
        assert now < 10
    assert values == sorted(values) and values[-1] == 1.0
    assert list(dict.fromkeys(stages)) == ["start", "rom", "quests", "write", "done"]
    assert now >= 4 * MIN_STAGE_SECONDS  # every stage was shown
    assert values[stages.index("write")] >= CHECKPOINTS["write"]  # jumped to the checkpoint


def test_progress_creeps_but_never_passes_the_next_checkpoint():
    bar = ProgressAnimator(0.0)
    bar.push_stage("rom")
    bar.push_stage("quests")
    values = [bar.tick(t / 10) for t in range(1, 400)]  # a long "quests" stage
    steps = [b - a for a, b in zip(values[20:], values[21:])]
    assert values[-1] < CHECKPOINTS["write"] and steps == sorted(steps, reverse=True)  # slowing down
    bar.set_quest_fraction(1.0)
    assert bar.tick(41) > values[-1]
