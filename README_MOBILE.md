# RABATY AI TRADER — iPhone + free hosting setup

This edition uses:
- Streamlit Community Cloud for the mobile web dashboard.
- GitHub Actions for scheduled scans and Telegram alerts (every 15 minutes, best effort).
- Public market data only. No exchange API key is needed.
- Signal-only behavior: it never places trades.

## Important free-tier limits
GitHub Actions scheduled runs are not guaranteed to start exactly on time; GitHub documents that schedule events can be delayed or dropped during heavy load. The minimum supported interval is 5 minutes. In public repositories, schedules can be disabled after 60 days without repository activity. Streamlit Community Cloud hibernates apps after 12 hours without traffic. This is suitable for testing, not dependable trading alerts or financial execution.

The Telegram workflow sends BUY/SELL alerts only. It does not run a continuously listening Telegram command bot. The `bot.py` polling version in this project requires an always-on host and is not used by the free scheduled workflow.

## A. Create the Telegram bot (iPhone)
1. Open Telegram and search for `@BotFather`.
2. Send `/newbot`.
3. Choose a display name, e.g. `RABATY AI TRADER`.
4. Choose a username ending in `bot`.
5. Copy the token. Keep it secret.
6. Open your new bot and press Start / send `/start`.
7. To get your numeric chat ID, open this URL in Safari after replacing TOKEN:
   `https://api.telegram.org/botTOKEN/getUpdates`
   Find `message` then `chat` then `id`. If result is empty, send a new message to your bot and refresh.
8. Never share the token or the getUpdates URL.

## B. Put the project on GitHub (iPhone)
1. Download and unzip `RABATY_AI_TRADER_mobile.zip` in the iPhone Files app.
2. In Safari, open `https://github.com` and create/sign in to an account.
3. Create a new repository named `rabaty-ai-trader`. For the easiest Streamlit connection, choose Public. Do not upload `.env` or any token.
4. Open the repository, choose Add file → Upload files.
5. Upload all project files and folders from the unzipped folder, including the hidden `.github` folder if the GitHub mobile page permits it. If hidden folders are not selectable, use GitHub's browser editor to create `.github/workflows/market-scan.yml` and paste its contents from the local file.
6. Commit the upload to the `main` branch.

## C. Add GitHub secrets
1. In the repository open Settings → Secrets and variables → Actions.
2. Choose New repository secret.
3. Add `TELEGRAM_BOT_TOKEN` with the token from BotFather.
4. Add `TELEGRAM_CHAT_ID` with your numeric Telegram chat ID.
5. Do not put either secret in source files, chat messages, or screenshots.

## D. Enable and test Telegram alerts
1. Open the repository's Actions tab.
2. If prompted, enable workflows.
3. Select `RABATY AI TRADER market scan`.
4. Press Run workflow for a first manual test.
5. Open the run and check its log. If data is available and a BUY/SELL setup qualifies, the bot sends a Telegram alert. If there is no setup, it intentionally sends no signal.
6. The schedule then attempts to scan every 15 minutes. This is best effort, not guaranteed real-time.

## E. Deploy the dashboard
1. Open `https://share.streamlit.io` in Safari.
2. Sign in with GitHub and authorize Streamlit.
3. Choose Create app / Deploy an app.
4. Select repository `rabaty-ai-trader`, branch `main`, and main file path `dashboard.py`.
5. Press Deploy. Wait for the build to finish.
6. Save the app URL to your iPhone Home Screen using Safari → Share → Add to Home Screen.
7. Streamlit Community Cloud apps can hibernate after 12 hours without traffic. Open the URL to wake the app.

## F. Verify data before relying on it
- Compare XAU/USD with your broker's quote; Yahoo Finance may be delayed, unavailable, or differ from broker pricing.
- XAUT/USDT is tokenized gold and may trade at a premium/discount to spot gold.
- Check that Bybit currently lists the XAUT/USDT spot symbol in your region.
- Backtest and paper trade the rules. Do not use this prototype as a promise of profit.
