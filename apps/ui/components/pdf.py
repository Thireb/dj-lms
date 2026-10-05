from apps.ui.components.base import Component


class PdfHeader(Component):
    template_name = "ui/components/pdf_header.html"

    def __init__(self, institute, **props):
        super().__init__(institute=institute, **props)
