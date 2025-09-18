# ZwiftPower Profile Checker

This script logs into **ZwiftPower** with your Zwift account and checks if the given Zwift IDs have a profile and which **Category (A/B/C/D/E)** they belong to.  
Results are written to a CSV file.

---

## Features
- Logs in via Zwift SSO (email + password).
- Input: CSV with `Email,FirstName,LastName,Country,ZwiftID`.
- Output: CSV with the same columns + `Category`.
- Rate limiting (2s/request) to avoid blocking.
- `.env` file support to keep credentials safe.

---

## Setup

### 1. Clone or copy this project
Put the files in a folder, e.g. `~/zwiftcheck`.

### 2. Create a virtual environment
```bash
cd ~/zwiftcheck
python3 -m venv venv
source venv/bin/activate


## Installation
### Install dependencies
python3 -m pip install -r requirements.txt

## Configuration
### Store Zwift credentials in .env

Create a .env file in the project folder:

ZWIFT_USER=your_email@example.com
ZWIFT_PASS=your_password

### Prepare the input CSV

Create a file zwift_ids.csv:

Email,FirstName,LastName,Country,ZwiftID
piet@example.com,Piet,Jansen,NL,123456
klaas@example.com,Klaas,Visser,BE,654321

## Run the script
python3 ZwiftPower.py

## License

Free to use for personal analysis. Please respect the ZwiftPower Terms of Service: data is for personal use only and not for commercial purposes.
