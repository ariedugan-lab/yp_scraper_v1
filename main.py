import os
from supabase import create_client, Client
from dotenv import load_dotenv
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

# Load environment variables from a .env file ------
load_dotenv()
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key) # Set up Supabase client

zip_start = os.environ.get("ZIP_START")
zip_end = os.environ.get("ZIP_END")

search_word = os.environ.get("SEARCH_WORD")

# Setting scraper configs ------