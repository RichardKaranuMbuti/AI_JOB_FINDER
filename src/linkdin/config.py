# Update this in config.py
import os

# LinkedIn Scraper Configuration

# Search parameters
JOB_TITLE = "AI Software Engineer"
LOCATION = "Remote"
NUM_PAGES = 1

# Output settings
CSV_FILENAME = "jobs.csv"
JOBS_CSV_FILENAME = "all-jobs.csv"

# Browser settings
USE_XDOTOOL = True
CHROME_DEBUG_PORT = 9222
PAGE_LOAD_WAIT_TIME = 6
ELEMENT_WAIT_TIME = 6
PAGE_NAVIGATION_WAIT_TIME = 3


# Get the directory of the config file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Create path to the database
DB_PATH = os.path.join(BASE_DIR, "linkedin_jobs.db")
# Set the database URL with the absolute path
DATABASE_URL = f"sqlite:///{DB_PATH}"



# For MySQL: DATABASE_URL = "mysql+pymysql://username:password@localhost/linkedin_jobs"
