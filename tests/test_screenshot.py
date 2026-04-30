from cua_lark.perception import screenshot


def test_rect_to_mss_coordinates_scales_logical_window_rect(monkeypatch) -> None:
    monkeypatch.setattr(screenshot, "_system_metrics", lambda: (1600, 1000))

    rect = screenshot._rect_to_mss_coordinates(
        (-7, -7, 1606, 958),
        {"left": 0, "top": 0, "width": 3200, "height": 2000},
    )

    assert rect == (0, 0, 3200, 1916)


def test_rect_to_mss_coordinates_keeps_physical_window_rect(monkeypatch) -> None:
    monkeypatch.setattr(screenshot, "_system_metrics", lambda: (3200, 2000))

    rect = screenshot._rect_to_mss_coordinates(
        (100, 50, 2500, 1500),
        {"left": 0, "top": 0, "width": 3200, "height": 2000},
    )

    assert rect == (100, 50, 2500, 1500)


def test_window_title_match_score_prefers_exact_title() -> None:
    assert screenshot._window_title_match_score("飞书", "飞书") == 0
    assert screenshot._window_title_match_score("飞书", "飞书 - notification") == 1
    assert screenshot._window_title_match_score("飞书", "browser tab - 飞书 docs") == 2
    assert screenshot._window_title_match_score("飞书", "ChatGPT") is None
