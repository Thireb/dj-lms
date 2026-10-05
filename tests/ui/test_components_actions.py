from apps.ui.components.actions import Button, ConfirmDialog, QuickAction, Toast


def test_button_renders() -> None:
    html = str(Button("Save changes", icon="check"))
    assert "Save changes" in html
    assert "btn-primary" in html


def test_quick_action_renders() -> None:
    html = str(QuickAction("Upload", "upload", "#"))
    assert "Upload" in html
    assert "quick-action" in html


def test_confirm_dialog_renders() -> None:
    html = str(ConfirmDialog("Sure?", "Yes", url="#"))
    assert "Sure?" in html
    assert "confirm-dialog" in html


def test_toast_renders() -> None:
    html = str(Toast("Saved", tone="success"))
    assert "Saved" in html
    assert "toast" in html
