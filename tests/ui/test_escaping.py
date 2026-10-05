from apps.ui.components.data import Badge, Column, DataTable

XSS = "<script>alert('x')</script>"


def test_badge_escapes_text() -> None:
    html = str(Badge(XSS))
    assert XSS not in html
    assert "&lt;script&gt;" in html


def test_data_table_escapes_cell_text() -> None:
    table = DataTable(
        rows=[{"name": XSS}],
        columns=[Column("name", "Name")],
    )
    html = str(table)
    assert XSS not in html
    assert "&lt;script&gt;" in html
