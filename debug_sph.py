import sys
import os

sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
import sph_client
import json
from bs4 import BeautifulSoup

load_dotenv()

api = sph_client.SchulportalHessenAPI()
api.login(
    os.getenv("LANIS_API_SCHOOL_ID"),
    os.getenv("LANIS_API_USERNAME"),
    os.getenv("LANIS_API_PASSWORD"),
)

# Check submissions
subs = api.meinunterricht_get_submissions()
print("=== SUBMISSIONS ===")
print(json.dumps(subs, ensure_ascii=False, indent=2)[:3000])

# Check course overview
overview = api.meinunterricht_get_overview()
print("\n=== COURSE OVERVIEW ===")
print(json.dumps(overview, ensure_ascii=False, indent=2)[:3000])
