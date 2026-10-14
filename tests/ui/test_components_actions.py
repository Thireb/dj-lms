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


def test_confirm_dialog_posts_with_csrf_when_request_given(rf) -> None:
    from apps.ui.components.actions import ConfirmDialog
    from django.middleware.csrf import get_token

    request = rf.get("/")
    get_token(request)
    html = ConfirmDialog(
        "Deactivate Demo?",
        "Deactivate",
        url="/super/institutes/1/status/",
        fields=[("action", "deactivate")],
    ).render(request=request)
    assert '<form method="post" action="/super/institutes/1/status/"' in html
    assert 'name="csrfmiddlewaretoken"' in html
    assert 'name="action" value="deactivate"' in html
    assert "Cancel" in html


def test_copy_field_renders_value_readonly() -> None:
    from apps.ui.components.actions import CopyField

    html = str(CopyField("Set-password link", "https://example.com/x/"))
    assert "readonly" in html
    assert 'value="https://example.com/x/"' in html
    assert "Copy link" in html


def test_toast_tones_use_theme_colors() -> None:
    assert "border-success" in str(Toast("Saved", tone="success"))
    assert "border-danger" in str(Toast("Failed", tone="error"))
    assert "border-border" in str(Toast("Note", tone="info"))


def test_disabled_button_is_a_state_not_a_link() -> None:
    from apps.ui.components.actions import Button

    html = str(Button("Join opens soon", url="/x/", disabled=True, title="At 3 PM"))

    assert "<a " not in html
    assert 'type="button" class="btn btn-primary" disabled title="At 3 PM"' in html


def test_post_button_posts_with_csrf_to_a_new_tab() -> None:
    from apps.ui.components.actions import PostButton
    from django.test import RequestFactory

    request = RequestFactory().get("/")
    html = PostButton("Join", "/student/lectures/1/join/", new_tab=True).render(
        request=request
    )
    plain = str(PostButton("Send", "/x/"))

    assert '<form method="post" action="/student/lectures/1/join/"' in html
    assert 'target="_blank" rel="noopener noreferrer"' in html
    assert 'name="csrfmiddlewaretoken"' in html
    assert 'type="submit"' in html
    assert "target=" not in plain
