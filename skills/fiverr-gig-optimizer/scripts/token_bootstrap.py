"""One-time, guided Hugging Face token bootstrap for opt-in federation.

Contributing opens a PR under the user's OWN Hugging Face identity, so it needs
their write token. That consent gate is deliberate — it keeps the project
local-first (nothing leaves the machine without an explicit, authenticated act)
and keeps the shared dataset spam-resistant. This module makes acquiring the
token a single browser click plus one paste, cached forever, instead of a manual
env-var dance.

Resolution order:
  1. ``$HF_TOKEN``                    (CI / power users)
  2. ``huggingface_hub`` cached token (set once, reused forever)
  3. interactive guided bootstrap     (open the pre-scoped token page, paste once,
                                        cache via ``huggingface_hub.login``)

Non-interactive callers (an agent/skill running the script) get the URL and a
clear instruction printed and a ``None`` return, so the agent can surface the
link, collect the pasted token, and re-run with it. No background upload ever
happens; this only ever *reads* or *caches* a token the user chose to provide.
"""
from __future__ import annotations

import os
import sys


def token_page_url() -> str:
    """Link to the fine-grained-token creation page (user ticks Write on the repo)."""
    return "https://huggingface.co/settings/tokens/new?tokenType=fineGrained"


def guidance(dataset_repo: str) -> str:
    """The human-readable one-time-setup instructions (shared by CLI + reminders)."""
    return (
        "To contribute you need a Hugging Face write token (one time only):\n"
        f"  1. Open: {token_page_url()}\n"
        "     Create a *fine-grained* token; under 'Repository permissions' add\n"
        f"     '{dataset_repo}' and tick Write.\n"
        "  2. Click 'Create token' and copy it.\n"
        "  3. Paste it when prompted — it is cached locally and never asked for again."
    )


def bootstrap_token(dataset_repo: str, *, allow_prompt: bool | None = None) -> str | None:
    """Return an HF token, guiding a one-time setup if none is cached.

    ``allow_prompt`` forces (True) or forbids (False) the interactive paste;
    the default auto-detects an interactive terminal. Returns ``None`` only when
    no token is available and the user did not provide one.
    """
    env = os.environ.get("HF_TOKEN")
    if env:
        return env.strip()
    try:  # a token cached by a previous run / `hf auth login`
        from huggingface_hub import get_token

        cached = get_token()
        if cached:
            return cached
    except Exception:
        pass

    if allow_prompt is None:
        allow_prompt = sys.stdin.isatty()

    print("\n" + guidance(dataset_repo))
    if not allow_prompt:
        # Agent / non-interactive: surface the link and let the caller collect the
        # paste, then re-run with --token <paste> (or HF_TOKEN set).
        print(
            "\n[no token] Not an interactive terminal. Open the link above, create "
            "the token, then re-run with --token <paste> (or set HF_TOKEN)."
        )
        return None

    try:
        import webbrowser

        webbrowser.open(token_page_url())
    except Exception:
        pass
    try:
        pasted = input("\nPaste HF token here (or press Enter to skip): ").strip()
    except EOFError:
        pasted = ""
    if not pasted:
        print("[skipped] No token entered; nothing was uploaded.")
        return None
    try:  # cache so it is never requested again
        from huggingface_hub import login

        login(token=pasted, add_to_git_credential=False)
    except Exception as exc:
        print(f"[warn] Could not cache the token ({exc}); using it for this run only.")
    return pasted
