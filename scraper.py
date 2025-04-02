import time
import csv
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from chrome_setup import open_linkedin_in_active_chrome
import config

def scrape_linkedin_jobs(job_title=None, location=None, num_pages=None, use_xdotool=None):
    """
    Scrape LinkedIn jobs using a two-step approach:
    1. Use xdotool to open LinkedIn in the current Chrome window
    2. Use regular Selenium to scrape the data
    
    Args:
        job_title (str, optional): Job title to search for. Defaults to config value.
        location (str, optional): Location to search in. Defaults to config value.
        num_pages (int, optional): Number of pages to scrape. Defaults to config value.
        use_xdotool (bool, optional): Whether to use xdotool. Defaults to config value.
    """
    # Use provided parameters or fall back to config values
    job_title = job_title if job_title is not None else config.JOB_TITLE
    location = location if location is not None else config.LOCATION
    num_pages = num_pages if num_pages is not None else config.NUM_PAGES
    use_xdotool = use_xdotool if use_xdotool is not None else config.USE_XDOTOOL
    
    # Output information about the scraping job
    print(f"Starting LinkedIn job search for '{job_title}' in '{location}'")
    print(f"Scraping {num_pages} page(s)")
    
    # Get the filename from config
    csv_filename = config.CSV_FILENAME
    
    # Step 1: Open LinkedIn in the active Chrome window
    if use_xdotool:
        success = open_linkedin_in_active_chrome(job_title, location)
        if not success:
            print("Failed to open LinkedIn in active Chrome window")
            return
        
        # Give time for the page to load
        print("Waiting for LinkedIn to load...")
        time.sleep(config.PAGE_LOAD_WAIT_TIME)
    
    # Step 2: Create a new Selenium instance to scrape the data
    options = Options()
    options.add_argument("--start-maximized")
    
    # Navigate to LinkedIn jobs search directly in this new browser
    driver = webdriver.Chrome(options=options)
    
    all_jobs = []
    
    try:
        # Loop through the specified number of pages
        for page in range(num_pages):
            # Calculate the start parameter for pagination
            # LinkedIn uses &start=25 for page 2, &start=50 for page 3, etc.
            start_param = 25 * page
            
            # Construct search URL with pagination parameter
            if page == 0:
                search_url = f"https://www.linkedin.com/jobs/search/?keywords={job_title}&location={location}"
            else:
                search_url = f"https://www.linkedin.com/jobs/search/?keywords={job_title}&location={location}&start={start_param}"
            
            print(f"Navigating to page {page + 1} with URL: {search_url}")
            driver.get(search_url)
            
            # Use WebDriverWait for better reliability
            wait = WebDriverWait(driver, config.ELEMENT_WAIT_TIME)
            
            # Wait for job listings to load
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'jobs-search__results-list')))
            
            # Additional wait time to ensure full page load
            time.sleep(config.PAGE_NAVIGATION_WAIT_TIME)
            
            # Get page source and parse it
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Find all job listings
            job_cards = soup.find_all('div', class_='base-card')
            
            if not job_cards:
                print("No job listings found. LinkedIn may have changed their HTML structure.")
                # Try alternative selectors
                job_cards = soup.find_all('li', class_='jobs-search-results__list-item')
                
                if not job_cards:
                    print("Still no job listings found. Trying different approach...")
                    # Try to find job cards by their job ID
                    job_cards = soup.find_all('div', attrs={'data-job-id': True})
            
            print(f"Found {len(job_cards)} job listings on page {page + 1}")
            
            # Process job cards
            for job_card in job_cards:
                try:
                    # Extract job details with different potential selectors
                    job_title_tag = job_card.find('h3', class_='base-search-card__title') or job_card.find('h3', class_='job-card-list__title')
                    job_title_text = job_title_tag.get_text(strip=True) if job_title_tag else 'N/A'
                    
                    company_name_tag = job_card.find('h4', class_='base-search-card__subtitle') or job_card.find('a', class_='job-card-container__company-name')
                    company_name = company_name_tag.get_text(strip=True) if company_name_tag else 'N/A'
                    
                    job_location_tag = job_card.find('span', class_='job-search-card__location') or job_card.find('li', class_='job-card-container__metadata-item')
                    job_location = job_location_tag.get_text(strip=True) if job_location_tag else 'N/A'
                    
                    # Try different date selectors
                    job_posting_date_tag = (
                        job_card.find('time', class_='job-search-card__listdate') or 
                        job_card.find('time') or
                        job_card.find('div', class_='job-card-container__footer-item')
                    )
                    job_posting_date = job_posting_date_tag.get_text(strip=True) if job_posting_date_tag else 'N/A'
                    
                    # Try to find job link
                    job_link_tag = job_card.find('a', class_='base-card__full-link') or job_card.find('a', class_='job-card-list__title')
                    job_link = job_link_tag.get('href') if job_link_tag else 'N/A'
                    
                    # Add job to our collection
                    all_jobs.append({
                        'Job Title': job_title_text,
                        'Company Name': company_name,
                        'Location': job_location,
                        'Posting Date': job_posting_date,
                        'Job URL': job_link
                    })
                except Exception as e:
                    print(f"Error processing job card: {e}")
                    continue
        
        # Write all collected jobs to CSV
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['Job Title', 'Company Name', 'Location', 'Posting Date', 'Job URL']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for job in all_jobs:
                writer.writerow(job)
        
        print(f"Job details have been written to '{csv_filename}' successfully! Found {len(all_jobs)} jobs.")
        
    except Exception as e:
        print(f"An error occurred during scraping: {e}")
    finally:
        # Close the Selenium driver
        driver.quit()