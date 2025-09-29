from app.stats import SessionStats, bump, load_from


def test_bump_win_and_winrate():
    s = SessionStats()
    s = bump(s, "win")
    assert s.fights == 1
    assert s.wins == 1
    assert s.losses == 0
    assert s.draws == 0
    assert round(s.winrate, 3) == 1.0


def test_bump_mixed():
    s = SessionStats()
    for r in ["win", "loss", "draw", "win"]:
        s = bump(s, r)
    assert (s.fights, s.wins, s.losses, s.draws) == (4, 2, 1, 1)
    assert round(s.winrate, 2) == 0.50  # 2/4


def test_load_from_partial_dict():
    raw = {"wins": 3}  # остальные поля по нулям
    s = load_from(raw)
    assert (s.fights, s.wins, s.losses, s.draws) == (0, 3, 0, 0)
