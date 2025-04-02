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

def scrape_linkedin_jobs_from_global_search(job_title=None, location=None, num_pages=None, use_xdotool=None):
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

def scrape_linkedin_jobs_from_jobs_search(job_title=None, location=None, num_pages=None, use_xdotool=None):
    """
    Scrape LinkedIn jobs from the Jobs menu search with improved error handling
    and more robust element selection.
    
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
    print(f"Starting LinkedIn job search (from Jobs menu) for '{job_title}' in '{location}'")
    print(f"Scraping {num_pages} page(s)")
    
    # Get the filename from config
    csv_filename = config.JOBS_CSV_FILENAME
    
    # Step 1: Open LinkedIn in the active Chrome window if using xdotool
    if use_xdotool:
        # Use the existing function with job_title and location parameters
        success = open_linkedin_in_active_chrome(job_title, location)
        
        if not success:
            print("Failed to open LinkedIn Jobs in active Chrome window")
            return
        
        # Give time for the page to load
        print("Waiting for LinkedIn Jobs to load...")
        time.sleep(config.PAGE_LOAD_WAIT_TIME)
    
    # Step 2: Create a new Selenium instance to scrape the data
    options = Options()
    options.add_argument("--start-maximized")
    
    # Navigate to LinkedIn jobs search directly in this new browser
    driver = webdriver.Chrome(options=options)
    
    all_jobs = []
    base_linkedin_url = "https://www.linkedin.com"
    
    try:
        # Loop through the specified number of pages
        for page in range(num_pages):
            # Calculate the start parameter for pagination
            # LinkedIn uses &start=25 for page 2, &start=50 for page 3, etc.
            start_param = 25 * page
            
            # Construct search URL with pagination parameter and encode spaces properly
            if page == 0:
                search_url = f"https://www.linkedin.com/jobs/search/?keywords={job_title.replace(' ', '%20')}&location={location.replace(' ', '%20')}"
            else:
                search_url = f"https://www.linkedin.com/jobs/search/?keywords={job_title.replace(' ', '%20')}&location={location.replace(' ', '%20')}&start={start_param}"
            
            print(f"Navigating to page {page + 1} with URL: {search_url}")
            driver.get(search_url)
            
            # Give the page time to load initially
            time.sleep(5)
            
            # Wait for any of the possible job container elements to be present
            wait = WebDriverWait(driver, config.ELEMENT_WAIT_TIME)
            try:
                # Try multiple possible selectors for the job results container
                selectors = [
                    "div.jobs-search-results-list",
                    "ul.jobs-search__results-list",
                    "div.scaffold-layout__list",
                    "ul.osvXwttVlxSToASQQxfDDAjwVGNfaCA"  # From your HTML example
                ]
                
                for selector in selectors:
                    try:
                        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                        print(f"Found job results container using selector: {selector}")
                        break
                    except:
                        continue
                
                # Additional wait time to ensure full page load
                time.sleep(config.PAGE_NAVIGATION_WAIT_TIME)
            except Exception as e:
                print(f"Error waiting for job results to load: {e}")
                print("Continuing anyway and attempting to parse the page...")
            
            # Get page source and parse it
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Try different selectors for job cards based on the HTML structure you provided
            job_cards = []
            
            # Method 1: Find by data-job-id attribute
            job_cards = soup.find_all('div', attrs={'data-job-id': True})
            
            # Method 2: Try li elements with occludable-update class
            if not job_cards:
                job_cards = soup.find_all('li', class_='occludable-update')
            
            # Method 3: Try base-card class
            if not job_cards:
                job_cards = soup.find_all('div', class_='base-card')
            
            # Method 4: Try job-card-container class
            if not job_cards:
                job_cards = soup.find_all('div', class_=lambda c: c and 'job-card-container' in c)
            
            # Method 5: Try list items in the job results list
            if not job_cards:
                results_list = soup.find('ul', class_=lambda c: c and 'osvXwttVlxSToASQQxfDDAjwVGNfaCA' in c)
                if results_list:
                    job_cards = results_list.find_all('li')
            
            print(f"Found {len(job_cards)} job listings on page {page + 1}")
            
            # Process job cards
            for job_card in job_cards:
                try:
                    # Extract job ID - first try to get it directly from the job card
                    job_id = None
                    
                    # Try to get job_id from the div with data-job-id attribute
                    job_div = job_card.find('div', attrs={'data-job-id': True})
                    if job_div:
                        job_id = job_div.get('data-job-id', 'N/A')
                    # If not found, try occludable attribute
                    elif job_card.has_attr('data-occludable-job-id'):
                        job_id = job_card.get('data-occludable-job-id', 'N/A')
                    else:
                        job_id = 'N/A'
                    
                    # Find the job title - try multiple approaches
                    job_title_text = 'N/A'
                    
                    # Method 1: Look for elements with aria-label
                    job_title_tag = job_card.find('a', attrs={'aria-label': True})
                    if job_title_tag:
                        job_title_text = job_title_tag['aria-label']
                    
                    # Method 2: Look for specific class
                    if job_title_text == 'N/A':
                        title_classes = ['job-card-list__title', 'base-search-card__title', 'job-card-container__link']
                        for cls in title_classes:
                            title_tag = job_card.find(['a', 'h3'], class_=cls)
                            if title_tag:
                                job_title_text = title_tag.get_text(strip=True)
                                break
                    
                    # Method 3: Look for strong tag inside span
                    if job_title_text == 'N/A':
                        span_with_strong = job_card.find('span', attrs={'aria-hidden': 'true'})
                        if span_with_strong and span_with_strong.find('strong'):
                            job_title_text = span_with_strong.find('strong').get_text(strip=True)
                    
                    # Extract job URL
                    job_link = 'N/A'
                    job_link_tag = job_card.find('a', href=lambda h: h and '/jobs/view/' in h)
                    
                    if job_link_tag:
                        job_link = job_link_tag.get('href')
                        # Ensure it's a full URL
                        if job_link and not job_link.startswith('http'):
                            job_link = base_linkedin_url + job_link
                    
                    # Find company name - try multiple approaches
                    company_name = 'N/A'
                    
                    # Method 1: Look for specific class with company name
                    company_tag = job_card.find('span', class_=lambda c: c and 'qHYMDgztNEREKlSMgIjhyyyqAxxeVviD' in c)
                    if company_tag:
                        company_name = company_tag.get_text(strip=True)
                    
                    # Method 2: Look for subtitle div
                    if company_name == 'N/A':
                        subtitle_div = job_card.find('div', class_='artdeco-entity-lockup__subtitle')
                        if subtitle_div:
                            company_name = subtitle_div.get_text(strip=True)
                    
                    # Method 3: Look for h4 with company name class
                    if company_name == 'N/A':
                        h4_tag = job_card.find('h4', class_=lambda c: c and 'base-search-card__subtitle' in c)
                        if h4_tag:
                            company_name = h4_tag.get_text(strip=True)
                    
                    # Find location - try multiple approaches
                    job_location = 'N/A'
                    
                    # Method 1: Look for specific class with location
                    location_li = job_card.find('li', class_=lambda c: c and 'bKQmZihARnOXesSdpcmicRgZiMVAUmlKncY' in c)
                    if location_li:
                        location_span = location_li.find('span')
                        if location_span:
                            job_location = location_span.get_text(strip=True)
                    
                    # Method 2: Look for span with dir=ltr
                    if job_location == 'N/A':
                        location_span = job_card.find('span', attrs={'dir': 'ltr'})
                        if location_span and not location_span.find('strong'):  # Exclude job title spans
                            job_location = location_span.get_text(strip=True)
                    
                    # Method 3: Look for job-search-card__location class
                    if job_location == 'N/A':
                        location_span = job_card.find('span', class_='job-search-card__location')
                        if location_span:
                            job_location = location_span.get_text(strip=True)
                    
                    # Check if it's Easy Apply
                    is_easy_apply = 'No'
                    easy_apply_span = job_card.find('span', string=lambda s: s and 'Easy Apply' in s)
                    if easy_apply_span:
                        is_easy_apply = 'Yes'
                    
                    # Add job to our collection
                    all_jobs.append({
                        'Job ID': job_id,
                        'Job Title': job_title_text,
                        'Company Name': company_name,
                        'Location': job_location,
                        'Easy Apply': is_easy_apply,
                        'Job URL': job_link
                    })
                    
                except Exception as e:
                    print(f"Error processing job card: {e}")
                    continue
            
            # If we didn't find any job cards using the direct methods, try a more general approach
            if len(all_jobs) == 0:
                print("No job cards found with standard methods. Trying a more general approach...")
                
                # Look for any elements that might contain job information
                potential_cards = soup.find_all(['div', 'li'], attrs={'class': True})
                
                for card in potential_cards:
                    try:
                        # Look for elements that might contain a job title
                        title_elements = card.find_all(['a', 'h3', 'strong', 'span'], string=True)
                        
                        for title_elem in title_elements:
                            title_text = title_elem.get_text(strip=True)
                            
                            # If we find something that looks like a job title
                            if title_text and len(title_text) > 5 and not title_text.startswith('http'):
                                print(f"Found potential job title: {title_text}")
                                
                                # Try to find a URL near this title
                                nearby_link = card.find('a', href=True)
                                job_link = nearby_link['href'] if nearby_link else 'N/A'
                                
                                # Add this as a potential job
                                all_jobs.append({
                                    'Job ID': 'unknown',
                                    'Job Title': title_text,
                                    'Company Name': 'unknown',
                                    'Location': 'unknown',
                                    'Easy Apply': 'unknown',
                                    'Job URL': job_link
                                })
                                break
                            
                    except Exception as e:
                        print(f"Error in general approach: {e}")
                        continue
        
        # Write all collected jobs to CSV
        if all_jobs:
            with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['Job ID', 'Job Title', 'Company Name', 'Location', 'Easy Apply', 'Job URL']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for job in all_jobs:
                    writer.writerow(job)
            
            print(f"Job details have been written to '{csv_filename}' successfully! Found {len(all_jobs)} jobs.")
        else:
            print("No jobs were found to write to CSV.")
        
    except Exception as e:
        print(f"An error occurred during scraping: {e}")
        # Print traceback for more detailed error information
        import traceback
        traceback.print_exc()
    finally:
        # Close the Selenium driver
        driver.quit()
