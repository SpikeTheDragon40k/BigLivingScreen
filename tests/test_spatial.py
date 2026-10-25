from living_room.ui.spatial import Rect, find_next


def grid(cols, rows, w=100, h=100, gap=20, y0=0):
    return {(c, r): Rect(c * (w + gap), y0 + r * (h + gap), w, h) for c in range(cols) for r in range(rows)}


def nav(cells, start, direction):
    return find_next(cells[start], [(k, v) for k, v in cells.items() if k != start], direction)


def test_grid_moves():
    g = grid(4, 3)
    assert nav(g, (1, 1), "right") == (2, 1)
    assert nav(g, (1, 1), "left") == (0, 1)
    assert nav(g, (1, 1), "up") == (1, 0)
    assert nav(g, (1, 1), "down") == (1, 2)


def test_edges_return_none():
    g = grid(3, 2)
    assert nav(g, (2, 0), "right") is None
    assert nav(g, (0, 0), "up") is None


def test_down_prefers_next_row_over_aligned_far_row():
    # Favorites: row of 3 then a row with 1 card; below, a 4-wide grid.
    cells = {("fav", c, 0): Rect(c * 320, 0, 300, 260) for c in range(3)}
    cells[("fav", 0, 1)] = Rect(0, 280, 300, 260)
    cells.update({("all", c): Rect(c * 260, 620, 240, 200) for c in range(4)})
    assert nav(cells, ("fav", 2, 0), "down") == ("fav", 0, 1)
    assert nav(cells, ("fav", 0, 1), "down") == ("all", 0)


def test_header_buttons_reachable():
    cells = grid(3, 1, y0=200)
    cells["settings"] = Rect(500, 0, 60, 60)
    assert nav(cells, (2, 0), "up") == "settings"
    assert nav(cells, "settings", "down") == (2, 0)


def test_right_at_row_end_does_not_jump_rows():
    cells = grid(3, 2, y0=200)
    cells["settings"] = Rect(500, 0, 60, 60)
    assert nav(cells, (2, 0), "right") is None
    assert nav(cells, (2, 1), "right") is None
