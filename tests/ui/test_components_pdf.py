from apps.ui.components.pdf import PdfHeader
from tests.ui.fixtures.sample_ui import fake_institute


def test_pdf_header_renders() -> None:
    html = str(PdfHeader(fake_institute()))
    assert "pdf-header" in html
    assert "Demo institute" in html
