from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.http import HttpRequest, HttpResponse
from shop.functions.tweet import TwitterAPI  # your class
from requests_oauthlib import OAuth2Session
from django.conf import settings


@login_required
def start_auth(request):
    api = TwitterAPI()
    auth_url = api.begin_oauth()

    # Persist PKCE + state for the callback request
    request.session["tw_code_verifier"] = api.code_verifier
    request.session["tw_state"] = getattr(api, "_state", None)

    return redirect(auth_url)

@login_required
def callback(request):
    # Provider error returned?
    if request.GET.get("error"):
        messages.error(request, request.GET.get("error_description") or request.GET.get("error"))
        return redirect(reverse("product_list"))

    api = TwitterAPI()

    # Restore PKCE verifier + expected state
    api.code_verifier = request.session.pop("tw_code_verifier", None)
    expected_state = request.session.pop("tw_state", None)

    # Rebuild OAuth2Session on this fresh instance
    if api.session is None:
        api.session = OAuth2Session(
            client_id=settings.TWITTER_CLIENT_ID,
            redirect_uri=settings.TWITTER_REDIRECT_URI,
            scope=settings.TWITTER_SCOPES,
        )

    api.finish_oauth(request.build_absolute_uri(), expected_state=expected_state)
    messages.success(request, "Twitter connected.")
    return redirect(reverse("product_list"))