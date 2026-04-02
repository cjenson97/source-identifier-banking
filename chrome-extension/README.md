# Chrome Extension: Banking Compliance Source Finder

## Load in Chrome

1. Open `chrome://extensions`
2. Turn on **Developer mode** (top-right)
3. Click **Load unpacked**
4. Select this folder: `chrome-extension`
5. Pin and open **Banking Compliance Source Finder**

## Usage

1. In **Already Covered Domains**, paste domains you already monitor.
2. Click **Run Now**.
3. Review **Findings** (only net-new domains).
4. Click **Export Findings CSV**.

## Notes

- The extension fetches from public web sources directly (GDELT, Google News RSS, regulator RSS feeds).
- Existing covered domains are excluded using exact and parent/subdomain matching.
- Notifications require Chrome extension notifications permission (already requested in manifest).
