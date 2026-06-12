from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

# site_settings reaches the shared navbar/footer via the
# landing.context_processors.site_settings context processor — no need to pass
# it from each view.


def login_view(request):
    """Log in with email and password; redirect to landing on success."""
    if request.user.is_authenticated:
        return redirect("/")
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, email=email, password=password)
        if user is not None:
            login(request, user)
            next_url = request.POST.get("next") or request.GET.get("next") or "/"
            return redirect(next_url)
        # Invalid credentials
        messages.error(request, _("Invalid email or password."))
    return render(request, "login.html")


def signup_view(request):
    """Register a new account with name, email, and password, then log in."""
    if request.user.is_authenticated:
        return redirect("/")
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        User = get_user_model()

        if not (name and email and password):
            messages.error(request, _("Please fill in all fields."))
        elif User.objects.filter(email__iexact=email).exists():
            messages.error(request, _("An account with this email already exists."))
        else:
            try:
                validate_password(password)
            except ValidationError as exc:
                for msg in exc.messages:
                    messages.error(request, msg)
            else:
                user = User.objects.create_user(
                    email=email, password=password, first_name=name
                )
                user = authenticate(request, email=email, password=password)
                if user is not None:
                    login(request, user)
                    return redirect("/")
        # Preserve typed values on error
        return render(request, "signup.html", {"name": name, "email": email})
    return render(request, "signup.html")
