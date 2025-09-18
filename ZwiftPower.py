import requests
from bs4 import BeautifulSoup
import csv
import time
import os
import pickle
from datetime import datetime, timedelta, UTC
from dotenv import load_dotenv

COOKIE_FILE = "cookies.pkl"
COOKIE_EXPIRY_HOURS = 4


class ZwiftPowerClient:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/111.0.0.0 Safari/537.36"
            )
        })

    def login(self):
        """Perform Zwift SSO login to ZwiftPower."""
        print("🔑 Performing login via Zwift SSO...")
        zwiftpower_login_url = (
            "https://zwiftpower.com/ucp.php?mode=login"
            "&login=external&oauth_service=oauthzpsso"
        )
        resp1 = self.session.get(zwiftpower_login_url, allow_redirects=False)

        if "Location" not in resp1.headers:
            raise RuntimeError("ZwiftPower login redirect not found.")

        zwift_login_url = resp1.headers["Location"]
        resp2 = self.session.get(zwift_login_url, allow_redirects=False)

        soup = BeautifulSoup(resp2.text, 'html.parser')
        form = soup.find('form')
        if not form or not form.get('action'):
            raise RuntimeError("Zwift login form not found.")

        action_url = form['action']
        payload = {
            tag['name']: tag.get('value', '')
            for tag in form.find_all('input') if tag.get('name')
        }
        payload['username'] = self.username
        payload['password'] = self.password
        if 'rememberMe' in payload:
            payload['rememberMe'] = 'on'

        resp3 = self.session.post(action_url, data=payload, allow_redirects=True)
        if resp3.status_code != 200:
            raise RuntimeError("Zwift login failed. Check credentials or login flow.")

        # Verify by requesting ZwiftPower homepage
        resp4 = self.session.get("https://zwiftpower.com/")
        if resp4.status_code == 200:
            if "Logout" in resp4.text or "profile.php" in resp4.text:
                print("✅ Successfully logged into ZwiftPower!")
                return
        raise RuntimeError("Could not verify login, ZwiftPower flow may have changed.")

    def _get_table_value(self, soup, header_name: str) -> str:
        """Find a <th> by text and return the corresponding <td> value."""
        th = soup.find("th", string=lambda x: x and header_name in x)
        if th:
            td = th.find_next("td")
            if td:
                bold = td.find("b")
                if bold:
                    return bold.get_text(strip=True)
                return td.get_text(strip=True)
        return "Not found"

    def _get_category_and_races(self, soup):
        """Extract Category letter and race count from the profile table."""
        th = soup.find("th", string=lambda x: x and "Category (Pace Group)" in x)
        if not th:
            return "No category found", "0"

        td = th.find_next("td")
        if not td:
            return "No category found", "0"

        # Category = span text
        span = td.find("span", class_=lambda c: c and c.startswith("label-cat-"))
        category = span.get_text(strip=True) if span else "No category found"

        # Races = remaining text in the <td>
        td_text = td.get_text(" ", strip=True)
        # Example: "B 45 races Info"
        td_text = td_text.replace(category, "").replace("Info", "").strip()
        races = "0"
        parts = td_text.split()
        if parts and parts[0].isdigit():
            races = parts[0]

        return category, races

    def get_rider_data(self, rider_id: int) -> dict:
        """Fetch Category, Races, zFTP, and Zwift Racing Score from a rider profile."""
        url = f"https://zwiftpower.com/profile.php?z={rider_id}"
        resp = self.session.get(url)
        if resp.status_code != 200:
            return {
                "Category": "Profile not found",
                "Races": "0",
                "zFTP": "Profile not found",
                "ZwiftRacingScore": "Profile not found"
            }

        soup = BeautifulSoup(resp.text, "html.parser")

        # Category + races
        category, races = self._get_category_and_races(soup)

        # zFTP
        zftp = self._get_table_value(soup, "zFTP")

        # Zwift Racing Score
        racing_score = self._get_table_value(soup, "Zwift Racing Score")

        return {
            "Category": category,
            "Races": races,
            "zFTP": zftp,
            "ZwiftRacingScore": racing_score
        }


# ---------------- Cookie handling ----------------

def save_cookies(session, filename=COOKIE_FILE):
    data = {
        "cookies": session.cookies,
        "timestamp": datetime.now(UTC)
    }
    with open(filename, "wb") as f:
        pickle.dump(data, f)


def load_cookies(session, filename=COOKIE_FILE, expiry_hours=COOKIE_EXPIRY_HOURS):
    if not os.path.exists(filename):
        return False

    with open(filename, "rb") as f:
        data = pickle.load(f)

    timestamp = data.get("timestamp")

    # Normalize old naive datetimes to UTC
    if timestamp and timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)

    if not timestamp or datetime.now(UTC) - timestamp > timedelta(hours=expiry_hours):
        print("⚠️ Cookie cache expired.")
        return False

    session.cookies.update(data["cookies"])
    print("🍪 Loaded cookies from cache.")
    return True


# ---------------- Main ----------------

def main():
    # Load credentials from .env
    load_dotenv()
    USERNAME = os.getenv("ZWIFT_USER")
    PASSWORD = os.getenv("ZWIFT_PASS")

    if not USERNAME or not PASSWORD:
        raise RuntimeError("Missing Zwift credentials in .env file.")

    INPUT_CSV = "zwift_ids.csv"
    OUTPUT_CSV = "zwiftpower_check.csv"

    client = ZwiftPowerClient(USERNAME, PASSWORD)

    # Try cookie cache first
    if load_cookies(client.session):
        resp = client.session.get("https://zwiftpower.com/")
        if resp.status_code == 200 and "Logout" in resp.text:
            print("✅ Session still valid, skipping login.")
        else:
            print("⚠️ Session invalid, logging in again...")
            client.login()
            save_cookies(client.session)
    else:
        print("No valid cookies found, logging in...")
        client.login()
        save_cookies(client.session)

    results = []
    with open(INPUT_CSV, newline="", encoding="utf-8") as infile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames + ["Category", "Races", "zFTP", "ZwiftRacingScore"]

        for idx, row in enumerate(reader, start=1):
            z_id = row["ZwiftID"].strip()
            print(f"[{idx}] Checking {z_id}...")
            rider_data = client.get_rider_data(z_id)
            row.update(rider_data)
            results.append(row)
            time.sleep(2)  # rate limiter

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"✅ Done! Results saved in {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
