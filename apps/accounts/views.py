"""Login, logout, and password setup views."""

from __future__ import annotations

from typing import Any

from django.contrib.auth import logout
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.forms import ForgotPasswordForm, LoginForm, SetPasswordForm
from apps.accounts.services import (
    TokenStatus,
    authenticate_user,
    login_with_remember_me,
    lookup_set_password_token,
    post_login_redirect_url,
    set_password_from_token,
)
from apps.ui.components.forms import CrispyForm, PublicPostForm
from apps.ui.components.layout import PageHeader, PublicFormShell, SectionCard


class PublicFormPage(TemplateView):
    """Unauthenticated form page using the public layout (no portal shell)."""

    template_name = "ui/layouts/public.html"
    title = ""
    form_class: type | None = None
    section_title = ""

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if request.user.is_authenticated and self.redirect_if_authenticated:
            return redirect(
                post_login_redirect_url(request.user, request.GET.get("next"))
            )
        return super().dispatch(request, *args, **kwargs)

    redirect_if_authenticated = True

    def get_form_kwargs(self) -> dict[str, Any]:
        return {}

    def get_form(self) -> Any:
        if self.form_class is None:
            raise ValueError("form_class is required")
        if self.request.method == "POST":
            form = self.form_class(self.request.POST, **self.get_form_kwargs())
        else:
            form = self.form_class(**self.get_form_kwargs())
        form.helper.disable_csrf = True
        return form

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return self.render_page(self.get_form())

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        return self.render_page(form)

    def form_valid(self, form: Any) -> HttpResponse:
        raise NotImplementedError

    def render_page(self, form: Any) -> HttpResponse:
        header = PageHeader(title=self.title)
        card = SectionCard(
            title=self.section_title or self.title,
            body=PublicPostForm(
                action=self.request.path,
                body=CrispyForm(form=form),
            ),
        )
        shell = PublicFormShell(page_title=self.title, header=header, content=card)
        return HttpResponse(shell.render(request=self.request))

    def get_cancel_url(self) -> str | None:
        return None


class LoginView(PublicFormPage):
    title = "Sign in"
    section_title = "Sign in"
    form_class = LoginForm
    redirect_if_authenticated = True

    def get_form_kwargs(self) -> dict[str, Any]:
        return {
            "cancel_url": reverse("accounts:forgot_password"),
            "next_url": self.request.GET.get("next"),
        }

    def form_valid(self, form: LoginForm) -> HttpResponse:
        user = authenticate_user(
            email=form.cleaned_data["email"],
            password=form.cleaned_data["password"],
        )
        if user is None:
            form.add_error("password", "Email or password is incorrect.")
            return self.render_page(form)
        remember = form.cleaned_data.get("remember_me", False)
        login_with_remember_me(self.request, user, remember=remember)
        next_url = self.request.GET.get("next") or self.request.POST.get("next")
        return redirect(post_login_redirect_url(user, next_url))


class ForgotPasswordView(PublicFormPage):
    title = "Forgot password"
    section_title = "Forgot password"
    form_class = ForgotPasswordForm
    redirect_if_authenticated = False

    message = (
        "We cannot reset your password here. Contact your institute admin "
        "to get a new sign-in link or password."
    )

    def get_form_kwargs(self) -> dict[str, Any]:
        return {"cancel_url": reverse("accounts:login")}

    def form_valid(self, form: ForgotPasswordForm) -> HttpResponse:
        return redirect("accounts:login")

    def render_page(self, form: Any) -> HttpResponse:
        from apps.ui.components.actions import Button
        from apps.ui.components.block_stack import BlockStack

        header = PageHeader(title=self.title)
        card = SectionCard(
            title=self.section_title,
            body=BlockStack(
                blocks=[
                    self.message,
                    Button(label="Back to sign in", url=reverse("accounts:login")),
                ]
            ),
        )
        shell = PublicFormShell(page_title=self.title, header=header, content=card)
        return HttpResponse(shell.render(request=self.request))


class SetPasswordView(PublicFormPage):
    title = "Set your password"
    section_title = "Set your password"
    form_class = SetPasswordForm
    redirect_if_authenticated = False

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.token_key = kwargs.get("token", "")
        lookup = lookup_set_password_token(self.token_key)
        self.token_lookup = lookup
        if lookup.status != TokenStatus.OK:
            return self.render_status_page(lookup.status)
        return super().dispatch(request, *args, **kwargs)

    def render_status_page(self, status: TokenStatus) -> HttpResponse:
        if status == TokenStatus.EXPIRED:
            message = "This link has expired. Ask your institute admin for a new one."
        elif status == TokenStatus.USED:
            message = "This link was already used. Sign in with your password."
        else:
            message = "This link is not valid. Ask your institute admin for a new one."
        header = PageHeader(title=self.title)
        card = SectionCard(title=self.section_title, body=message)
        shell = PublicFormShell(page_title=self.title, header=header, content=card)
        return HttpResponse(shell.render(request=self.request))

    def form_valid(self, form: SetPasswordForm) -> HttpResponse:
        token = self.token_lookup.token
        if token is None:
            return self.render_status_page(TokenStatus.MISSING)
        set_password_from_token(token=token, password=form.cleaned_data["password"])
        return redirect("accounts:login")


class LogoutView(View):
    """POST-only logout (Django 5 compatible)."""

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        logout(request)
        return HttpResponseRedirect(reverse_lazy("accounts:login"))

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return HttpResponse("Method not allowed", status=405)
