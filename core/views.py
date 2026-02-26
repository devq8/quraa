from django.contrib.auth import authenticate, login
from django.shortcuts import redirect, render


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
        from django.contrib import messages
        messages.error(request, "Invalid email or password.")
    return render(request, "registration/login.html")
