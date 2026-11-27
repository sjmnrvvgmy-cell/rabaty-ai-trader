import os
import requests


def send_signal_keyboard(text: str = "بۆ وەرگرتنی پشکنینی نوێ، دەست لە دوگمەی (سیگنال) بدە:") -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_ids_raw = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_ids_raw:
        raise ValueError("TELEGRAM_BOT_TOKEN یان TELEGRAM_CHAT_ID دیاری نەکراوە.")

    keyboard = {
        "keyboard": [[{"text": "سیگنال"}]],
        "resize_keyboard": True,
        "is_persistent": True,
    }

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for chat_id in [c.strip() for c in chat_ids_raw.split(",") if c.strip()]:
        resp = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text,
                "reply_markup": keyboard,
            },
            timeout=20,
        )
        resp.raise_for_status()


def trigger_github_scan() -> None:
    gh_token = os.environ.get("GITHUB_PAT", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    workflow_file = os.environ.get("GITHUB_WORKFLOW_FILE", "scan_5m.yml").strip()
    ref = os.environ.get("GITHUB_REF_NAME", "main").strip()

    if not gh_token or not repo:
        raise ValueError("GITHUB_PAT یان GITHUB_REPOSITORY دیاری نەکراوە.")

    url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_file}/dispatches"
    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json",
    }
    resp = requests.post(url, headers=headers, json={"ref": ref}, timeout=20)
    resp.raise_for_status()