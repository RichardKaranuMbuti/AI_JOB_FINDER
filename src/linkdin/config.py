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



# Database configuration
DATABASE_URL = "sqlite:///linkedin_jobs.db"  # For SQLite
# For MySQL: DATABASE_URL = "mysql+pymysql://username:password@localhost/linkedin_jobs"
