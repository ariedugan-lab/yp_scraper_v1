import os
import csv
import time
import random
from dotenv import load_dotenv
from supabase import create_client, Client
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

# -------------------------------------------------
# LOAD ENV
# -------------------------------------------------
load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

ZIP_STATE = os.environ["ZIP_STATE"].upper()
SEARCH_WORD = os.environ.get("SEARCH_WORD")
if not SEARCH_WORD:
    raise ValueError("SEARCH_WORD env var is required")
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", 100))

SCRAPER_NAME = f"yellowpages_papi_{ZIP_STATE}"
ZIP_FILE = "uszips.csv"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------------------------------------
# PROGRESS (configs TABLE)
# -------------------------------------------------
def load_last_zip():
    res = (
        supabase.table("configs")
        .select("last_zip")
        .eq("scraper_name", SCRAPER_NAME)
        .limit(1)
        .execute()
    )

    if res.data and res.data[0]["last_zip"] is not None:
        return str(res.data[0]["last_zip"]).zfill(5)

    return None


def save_progress(zipcode):
    supabase.table("configs").upsert(
        {
            "scraper_name": SCRAPER_NAME,
            "last_zip": int(zipcode),  # bigint-safe
        }
    ).execute()


# -------------------------------------------------
# LOAD ZIPS BY STATE
# -------------------------------------------------
def load_state_zips():
    zips = []

    with open(ZIP_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["state_id"].upper() == ZIP_STATE:
                zip_code = row["zip"].strip().zfill(5)
                if zip_code.isdigit():
                    zips.append(zip_code)

    return sorted(set(zips))


# -------------------------------------------------
# SUPABASE BUFFER
# -------------------------------------------------
buffer = []


def flush_buffer():
    global buffer

    if not buffer:
        return

    try:
        supabase.table("papi").insert(buffer).execute()
        print(f"🧠 Inserted {len(buffer)} rows into papi")
        buffer = []
    except Exception as e:
        print("❌ Supabase insert failed:", e)


# -------------------------------------------------
# SELENIUM SETUP
# -------------------------------------------------

#driver = uc.Chrome() # Uncomment this line to use undetected_chromedriver locally

def create_driver():
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--window-size=1920,1080")
    return uc.Chrome(options=options)

driver = create_driver()
# -------------------------------------------------
# SCRAPE PAGE
# -------------------------------------------------
def scrape_page():
    businesses = driver.find_elements(By.CLASS_NAME, "result")
    added = 0

    for biz in businesses:
        try:
            title_el = biz.find_element(By.CLASS_NAME, "business-name")
            title = title_el.text.strip()
            yp_link = title_el.get_attribute("href")

            website = None
            phone = None
            street = None
            locality = None

            try:
                website = biz.find_element(By.CLASS_NAME, "track-visit-website").get_attribute("href")
            except:
                pass

            try:
                phone = biz.find_element(By.CLASS_NAME, "phones").text
            except:
                pass

            try:
                street = biz.find_element(By.CLASS_NAME, "street-address").text
            except:
                pass

            try:
                locality = biz.find_element(By.CLASS_NAME, "locality").text
            except:
                pass

            buffer.append(
                {
                    "business_name": title,
                    "website": website,
                    "yp_link": yp_link,
                    "phone": phone,
                    "street": street,
                    "locality": locality,
                    "category": SEARCH_WORD,
                }
            )

            added += 1
            print(f"{title} | {website} | {phone}")

            if len(buffer) >= BATCH_SIZE:
                flush_buffer()

        except:
            pass

    return added


# -------------------------------------------------
# SCRAPE ZIP
# -------------------------------------------------
def scrape_zip(zipcode):
    print(f"\n===============================")
    print(f"🔎 SCRAPING {ZIP_STATE} ZIP: {zipcode}")
    print(f"===============================")

    driver.get("https://www.yellowpages.com")
    time.sleep(2)

    query_box = driver.find_element(By.ID, "query")
    loc_box = driver.find_element(By.ID, "location")

    query_box.clear()
    query_box.send_keys(SEARCH_WORD)

    loc_box.clear()
    loc_box.send_keys(zipcode)
    loc_box.send_keys(Keys.ENTER)

    time.sleep(3)

    empty_pages = 0
    page = 1

    while True:
        print(f"--- PAGE {page} ---")
        added = scrape_page()

        if added == 0:
            empty_pages += 1
        else:
            empty_pages = 0

        if empty_pages >= 4:
            print("❌ No more results for this ZIP.")
            break

        try:
            current_url = driver.current_url
            driver.find_element(By.CSS_SELECTOR, "a.next").click()
            time.sleep(4)

            if driver.current_url == current_url:
                break

            page += 1
        except:
            break


# -------------------------------------------------
# MAIN
# -------------------------------------------------
zips = load_state_zips()
last_zip = load_last_zip()
skip_mode = last_zip is not None

counter = 0

for zipcode in zips:
    if skip_mode:
        if zipcode == last_zip:
            skip_mode = False
        continue

    scrape_zip(zipcode)
    save_progress(zipcode)

    counter += 1
    time.sleep(random.uniform(3, 7))

    # Restart browser every 300 ZIPs
    if counter % 300 == 0:
        print("\n🔄 Restarting browser…")
        driver.quit()
        #driver = uc.Chrome()
        driver = create_driver()


flush_buffer()
driver.quit()

print(f"\n🏁 FINISHED STATE: {ZIP_STATE}")
