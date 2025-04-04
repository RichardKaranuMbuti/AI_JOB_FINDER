# Standard library imports
import asyncio
import concurrent.futures
import csv
import logging
import os
import re
import time
import traceback
from contextlib import contextmanager
from datetime import datetime

# Third-party library imports
import aiohttp
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from sqlalchemy import (Column, MetaData, String, Table, Text, create_engine,
                       insert, select, update)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

# Local application imports
import config
from chrome_setup import open_linkedin_in_active_chrome


async def fetch_job_details(session, job_id, job_title, location):
    """
    Fetch detailed job information using the job ID
    
    Args:
        session (aiohttp.ClientSession): HTTP session
        job_id (str): LinkedIn job ID
        job_title (str): Job title for URL construction
        location (str): Location for URL construction
        
    Returns:
        dict: Job details including description, criteria, applicants, etc.
    """
    # Construct the job detail URL
    detail_url = f"https://www.linkedin.com/jobs/search/?currentJobId={job_id}&keywords={job_title.replace(' ', '%20')}&location={location.replace(' ', '%20')}&position=1&pageNum=0"
    
    job_details = {
        'job_description': 'N/A',
        'seniority_level': 'N/A',
        'employment_type': 'N/A',
        'job_function': 'N/A',
        'industries': 'N/A',
        'applicants': 'N/A',
        'date_posted': 'N/A'
    }
    
    try:
        # We need to use Selenium here because the job details page has dynamic content
        options = Options()
        options.add_argument("--headless")  # Run in headless mode
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        driver = webdriver.Chrome(options=options)
        
        try:
            driver.get(detail_url)
            # Give the page time to load
            time.sleep(4)
            
            # Wait for the job description to load
            wait = WebDriverWait(driver, 10)
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.description__text")))
            except Exception as e:
                print(f"Timeout waiting for job description: {e}")
            
            # Get the page source and parse it
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Extract job description
            description_div = soup.find('div', class_='show-more-less-html__markup')
            if description_div:
                # Extract text and remove HTML tags
                job_details['job_description'] = description_div.get_text(strip=True, separator=" ")
            
            # Extract job criteria (Seniority level, Employment type, etc.)
            criteria_list = soup.find('ul', class_='description__job-criteria-list')
            if criteria_list:
                criteria_items = criteria_list.find_all('li', class_='description__job-criteria-item')
                for item in criteria_items:
                    header = item.find('h3', class_='description__job-criteria-subheader')
                    value = item.find('span', class_='description__job-criteria-text')
                    
                    if header and value:
                        header_text = header.get_text(strip=True).lower()
                        value_text = value.get_text(strip=True)
                        
                        if 'seniority level' in header_text:
                            job_details['seniority_level'] = value_text
                        elif 'employment type' in header_text:
                            job_details['employment_type'] = value_text
                        elif 'job function' in header_text:
                            job_details['job_function'] = value_text
                        elif 'industries' in header_text:
                            job_details['industries'] = value_text
            
            # Extract number of applicants or application clicks
            try:
                # First try for "num-applicants__caption" format
                applicants_span = soup.find('span', class_='num-applicants__caption')
                if not applicants_span:
                    applicants_span = soup.find('span', class_='num-applicants__caption topcard__flavor--metadata topcard__flavor--bullet')
                
                # If found, extract text
                if applicants_span:
                    job_details['applicants'] = applicants_span.get_text(strip=True)
                else:
                    # Try for "people clicked apply" format
                    clicked_apply_span = soup.find('span', class_='tvm__text tvm__text--positive')
                    if clicked_apply_span:
                        job_details['applicants'] = clicked_apply_span.get_text(strip=True)
                    else:
                        # Last resort: general approach to find any span with relevant text
                        for span in soup.find_all('span'):
                            span_text = span.get_text(strip=True).lower()
                            if 'applicants' in span_text or 'people clicked apply' in span_text:
                                job_details['applicants'] = span.get_text(strip=True)
                                break
            except Exception as e:
                print(f"Error extracting applicants info: {e}")
                job_details['applicants'] = None
            
            # Extract date posted
            time_tag = soup.find('time', attrs={'datetime': True})
            if time_tag:
                job_details['date_posted'] = time_tag.get('datetime')
            
        except Exception as e:
            print(f"Error fetching job details for job ID {job_id}: {e}")
        finally:
            driver.quit()
        
    except Exception as e:
        print(f"Error setting up browser for job details: {e}")
    
    return job_details


async def process_job_batch(jobs_batch, location, progress_bar):
    """Process a batch of jobs concurrently"""
    async with aiohttp.ClientSession() as session:
        tasks = []
        for job in jobs_batch:
            job_id = job['Job ID']
            job_title = job['Job Title']
            
            if job_id != 'N/A':
                task = fetch_job_details(session, job_id, job_title, location)
                tasks.append(task)
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks)
        
        # Update progress bar
        progress_bar.update(len(tasks))
        
        # Update job entries with the fetched details
        for i, job in enumerate(jobs_batch):
            if i < len(results) and job['Job ID'] != 'N/A':
                job_details = results[i]
                job.update(job_details)
        
        return jobs_batch


async def process_all_jobs(all_jobs, location, batch_size=5):
    """Process all jobs in batches with a progress bar"""
    # Filter out jobs without a job ID
    valid_jobs = [job for job in all_jobs if job['Job ID'] != 'N/A']
    
    total_jobs = len(valid_jobs)
    print(f"\nFetching detailed information for {total_jobs} jobs...")
    
    # Create progress bar
    progress_bar = tqdm(total=total_jobs, desc="Fetching job details")
    
    # Split jobs into batches
    batches = [valid_jobs[i:i+batch_size] for i in range(0, len(valid_jobs), batch_size)]
    
    # Process each batch
    processed_jobs = []
    for batch in batches:
        processed_batch = await process_job_batch(batch, location, progress_bar)
        processed_jobs.extend(processed_batch)
    
    progress_bar.close()
    
    # Merge processed jobs with jobs that had no ID
    invalid_jobs = [job for job in all_jobs if job['Job ID'] == 'N/A']
    all_processed_jobs = processed_jobs + invalid_jobs
    
    return all_processed_jobs


# Set up logging
def setup_logging():
    """Set up logging configuration."""
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, f"linkedin_scraper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger("linkedin_scraper")

# Create a logger
logger = setup_logging()

# Initialize database connection
def init_database(db_url):
    """Initialize database connection and tables."""
    engine = create_engine(db_url)
    metadata = MetaData()
    
    # Define the jobs table
    jobs_table = Table(
        'linkedin_jobs', 
        metadata,
        Column('job_id', String(50), primary_key=True),
        Column('job_title', String(255)),
        Column('company_name', String(255)),
        Column('location', String(255)),
        Column('job_url', String(500)),
        Column('job_description', Text),
        Column('seniority_level', String(100)),
        Column('employment_type', String(100)),
        Column('job_function', String(100)),
        Column('industries', String(255)),
        Column('applicants', String(50)),
        Column('date_posted', String(50)),
        Column('date_scraped', String(50))
    )
    
    # Create the table if it doesn't exist
    metadata.create_all(engine)
    
    return engine, jobs_table

# Session manager context
@contextmanager
def session_scope(engine):
    """Provide a transactional scope around a series of operations."""
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
        session.commit()
    except Exception as e:
        logger.error(f"Database session error: {e}")
        session.rollback()
        raise
    finally:
        session.close()

async def async_scrape_linkedin_jobs(job_title=None, location=None, num_pages=None, use_xdotool=None, batch_size=5, max_workers=5):
    """
    Asynchronously scrape LinkedIn jobs and their details
    
    Args:
        job_title (str, optional): Job title to search for. Defaults to config value.
        location (str, optional): Location to search in. Defaults to config value.
        num_pages (int, optional): Number of pages to scrape. Defaults to config value.
        use_xdotool (bool, optional): Whether to use xdotool. Defaults to config value.
        batch_size (int, optional): Size of job batches for processing. Defaults to 5.
        max_workers (int, optional): Maximum number of concurrent workers. Defaults to 5.
    """
    logger.info("Starting LinkedIn job scraping")
    
    # Initialize parameters with defaults if not provided
    params = initialize_parameters(job_title, location, num_pages, use_xdotool)
    
    # Initialize database
    db_engine, jobs_table = init_database(config.DATABASE_URL)
    
    # Initialize Selenium driver
    driver = initialize_selenium_driver()
    
    all_jobs = []
    processed_jobs = []
    
    try:
        # Set up the scraping environment (open LinkedIn in Chrome if using xdotool)
        if params['use_xdotool']:
            setup_linkedin_with_xdotool(params['job_title'], params['location'])
        
        # Scrape job listings from LinkedIn
        all_jobs = scrape_job_listings(driver, params['job_title'], params['location'], params['num_pages'])
        
        # Process jobs to get detailed information
        processed_jobs = await process_all_jobs(all_jobs, params['location'], batch_size=batch_size)
        
        # Save the collected jobs to both CSV and database
        # save_jobs_to_csv(processed_jobs, config.JOBS_CSV_FILENAME)
        save_jobs_to_database(processed_jobs, db_engine, jobs_table)
        
    except Exception as e:
        logger.error(f"Error in main scraping process: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Save what we have so far before failing
        if all_jobs:
            logger.info(f"Saving {len(all_jobs)} jobs collected before error occurred")
            try:
                save_jobs_to_csv(all_jobs, config.JOBS_CSV_FILENAME + ".partial")
                if processed_jobs:
                    save_jobs_to_database(processed_jobs, db_engine, jobs_table)
            except Exception as save_error:
                logger.error(f"Error saving partial data: {str(save_error)}")
    finally:
        # Close the Selenium driver
        driver.quit()
        logger.info("LinkedIn job scraping completed")

def initialize_parameters(job_title=None, location=None, num_pages=None, use_xdotool=None):
    """Initialize parameters with defaults from config if not provided."""
    params = {
        'job_title': job_title if job_title is not None else config.JOB_TITLE,
        'location': location if location is not None else config.LOCATION,
        'num_pages': num_pages if num_pages is not None else config.NUM_PAGES,
        'use_xdotool': use_xdotool if use_xdotool is not None else config.USE_XDOTOOL
    }
    
    # Output information about the scraping job
    logger.info(f"Starting LinkedIn job search for '{params['job_title']}' in '{params['location']}'")
    logger.info(f"Scraping {params['num_pages']} page(s)")
    
    return params

def initialize_selenium_driver():
    """Initialize and return a configured Selenium Chrome driver."""
    logger.info("Initializing Selenium Chrome driver")
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled") 
    options.add_experimental_option("excludeSwitches", ["enable-automation"]) 
    options.add_experimental_option("useAutomationExtension", False) 
    
    return webdriver.Chrome(options=options)

def setup_linkedin_with_xdotool(job_title, location):
    """Set up LinkedIn in an active Chrome window using xdotool."""
    logger.info("Setting up LinkedIn with xdotool")
    success = open_linkedin_in_active_chrome(job_title, location)
    
    if not success:
        logger.error("Failed to open LinkedIn Jobs in active Chrome window")
        return False
    
    # Give time for the page to load
    logger.info("Waiting for LinkedIn Jobs to load...")
    time.sleep(config.PAGE_LOAD_WAIT_TIME)
    return True

def scrape_job_listings(driver, job_title, location, num_pages):
    """Scrape job listings from LinkedIn pages."""
    logger.info(f"Scraping job listings for {job_title} in {location}")
    all_jobs = []
    base_linkedin_url = "https://www.linkedin.com"
    
    # Create a progress bar for page scraping
    with tqdm(total=num_pages, desc="Scraping job listings pages") as pbar:
        # Loop through the specified number of pages
        for page in range(num_pages):
            try:
                # Navigate to the job search page
                search_url = construct_search_url(job_title, location, page)
                
                logger.info(f"Navigating to page {page + 1} with URL: {search_url}")
                driver.get(search_url)
                
                # Wait for page to load and find job containers
                wait_for_job_container(driver)
                
                # Parse the page and extract job cards
                job_cards = extract_job_cards(driver)
                
                logger.info(f"Found {len(job_cards)} job listings on page {page + 1}")
                
                # Process job cards on this page
                jobs_from_page = process_job_cards(job_cards, base_linkedin_url, page)
                all_jobs.extend(jobs_from_page)
            
            except Exception as e:
                logger.error(f"Error scraping page {page + 1}: {str(e)}")
                logger.error(traceback.format_exc())
                # Continue with the next page
            
            # Update the page progress bar
            pbar.update(1)
    
    # If no jobs found, try alternative approach
    if len(all_jobs) == 0:
        logger.warning("No jobs found with standard approach. Trying alternative method.")
        all_jobs = try_alternative_job_extraction(driver)
    
    logger.info(f"Initial job scraping complete. Found {len(all_jobs)} jobs.")
    logger.info("Now fetching detailed information for jobs with valid Job IDs...")
    
    return all_jobs

def construct_search_url(job_title, location, page):
    """Construct LinkedIn job search URL with pagination."""
    start_param = 25 * page
    
    # Construct search URL with pagination parameter and encode spaces properly
    if page == 0:
        search_url = f"https://www.linkedin.com/jobs/search/?keywords={job_title.replace(' ', '%20')}&location={location.replace(' ', '%20')}"
    else:
        search_url = f"https://www.linkedin.com/jobs/search/?keywords={job_title.replace(' ', '%20')}&location={location.replace(' ', '%20')}&start={start_param}"
    
    return search_url

def wait_for_job_container(driver):
    """Wait for job container elements to load."""
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
            "ul.osvXwttVlxSToASQQxfDDAjwVGNfaCA"
        ]
        
        for selector in selectors:
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                logger.info(f"Found job results container using selector: {selector}")
                break
            except:
                continue
        
        # Additional wait time to ensure full page load
        time.sleep(config.PAGE_NAVIGATION_WAIT_TIME)
    except Exception as e:
        logger.warning(f"Error waiting for job results to load: {e}")
        logger.warning("Continuing anyway and attempting to parse the page...")

def extract_job_cards(driver):
    """Extract job card elements from the page."""
    page_source = driver.page_source
    soup = BeautifulSoup(page_source, 'html.parser')
    
    # Try different selectors for job cards based on the HTML structure
    job_cards = []
    
    # Method 1: Find by data-job-id attribute (MAIN METHOD)
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
    
    return job_cards

def process_job_cards(job_cards, base_linkedin_url, page):
    """Process job cards to extract basic job information."""
    page_jobs = []
    
    # Create a progress bar for processing jobs on this page
    with tqdm(total=len(job_cards), desc=f"Processing jobs on page {page+1}") as job_pbar:
        # Process job cards
        for job_card in job_cards:
            try:
                job_entry = extract_job_data_from_card(job_card, base_linkedin_url)
                
                # Add job to our collection
                page_jobs.append(job_entry)
                job_pbar.update(1)
                
            except Exception as e:
                logger.warning(f"Error processing job card: {e}")
                job_pbar.update(1)
                continue
    
    return page_jobs

def extract_job_data_from_card(job_card, base_linkedin_url):
    """Extract job data from a single job card."""
    # Extract job title
    job_title_text = extract_job_title(job_card)
    
    # Extract job URL
    job_link = extract_job_url(job_card, base_linkedin_url)
    
    # Find company name
    company_name = extract_company_name(job_card)
    
    # Find location
    job_location = extract_job_location(job_card)
    
    # Extract job ID
    job_id = extract_job_id(job_card, job_link)
    
    # Create and return job entry
    return {
        'Job ID': job_id,
        'Job Title': job_title_text,
        'Company Name': company_name,
        'Location': job_location,
        'Job URL': job_link,
        'job_description': 'N/A',
        'seniority_level': 'N/A',
        'employment_type': 'N/A',
        'job_function': 'N/A',
        'industries': 'N/A',
        'applicants': 'N/A',
        'date_posted': 'N/A'
    }

def extract_job_title(job_card):
    """Extract the job title from a job card."""
    job_title_text = 'N/A'
    
    # Method 1: Look for aria-label on anchor tag
    job_title_anchor = job_card.find('a', attrs={'aria-label': True})
    if job_title_anchor:
        job_title_text = job_title_anchor['aria-label']
    
    # Method 2: Look for <strong> inside span
    if job_title_text == 'N/A':
        title_span = job_card.find('span', attrs={'aria-hidden': 'true'})
        if title_span and title_span.find('strong'):
            job_title_text = title_span.find('strong').get_text(strip=True)
    
    # Method 3: Look for specific class names
    if job_title_text == 'N/A':
        title_classes = ['job-card-list__title', 'base-search-card__title', 'job-card-container__link']
        for cls in title_classes:
            title_tag = job_card.find(['a', 'h3'], class_=lambda c: c and cls in c)
            if title_tag:
                job_title_text = title_tag.get_text(strip=True)
                break
    
    return job_title_text

def extract_job_url(job_card, base_linkedin_url):
    """Extract the job URL from a job card."""
    job_link = 'N/A'
    job_link_tag = job_card.find('a', href=lambda h: h and '/jobs/view/' in h)
    
    if job_link_tag:
        job_link = job_link_tag.get('href')
        # Ensure it's a full URL
        if job_link and not job_link.startswith('http'):
            job_link = base_linkedin_url + job_link
    
    return job_link

def extract_company_name(job_card):
    """Extract the company name from a job card."""
    company_name = 'N/A'
    
    # Method 1: Look for the specific class
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
    
    return company_name

def extract_job_location(job_card):
    """Extract the job location from a job card."""
    job_location = 'N/A'
    
    # Method 1: Using exact class from your HTML
    location_li = job_card.find('li', class_=lambda c: c and 'bKQmZihARnOXesSdpcmicRgZiMVAUmlKncY' in c)
    if location_li:
        location_span = location_li.find('span')
        if location_span:
            job_location = location_span.get_text(strip=True)
    
    # Method 2: Look for span with dir=ltr
    if job_location == 'N/A':
        location_spans = job_card.find_all('span', attrs={'dir': 'ltr'})
        for span in location_spans:
            # Skip spans that are part of job title or Easy Apply
            parent_is_li = span.parent and span.parent.name == 'li'
            if parent_is_li and span.get_text(strip=True) != "Easy Apply":
                job_location = span.get_text(strip=True)
                break
    
    # Method 3: Look for job-search-card__location class
    if job_location == 'N/A':
        location_span = job_card.find('span', class_='job-search-card__location')
        if location_span:
            job_location = location_span.get_text(strip=True)
    
    return job_location

def extract_job_id(job_card, job_link):
    """Extract the job ID from a job card or its URL."""
    job_id = 'N/A'
    
    # Try to get job ID directly from card attribute
    if job_card.has_attr('data-job-id'):
        job_id = job_card['data-job-id']
    else:
        # If not found directly, extract from URL
        if job_link != 'N/A' and '/jobs/view/' in job_link:
            try:
                # Try various methods to extract job ID
                url_parts = job_link.split('/')
                for part in url_parts:
                    if 'at-' in part and '?' in part:
                        id_part = part.split('at-')[-1].split('?')[0]
                        numeric_id = ''.join(filter(str.isdigit, id_part))
                        if numeric_id:
                            job_id = numeric_id
                            break
                
                # If still no ID, try regex
                if job_id == 'N/A':
                    match = re.search(r'-(\d+)/?\?', job_link)
                    if match:
                        job_id = match.group(1)
            except Exception as e:
                logger.warning(f"Error extracting job ID from URL: {e}")
    
    return job_id

def try_alternative_job_extraction(driver):
    """Try alternative method to extract jobs when standard methods fail."""
    logger.info("No job cards found with standard methods. Trying a more general approach...")
    all_jobs = []
    
    page_source = driver.page_source
    soup = BeautifulSoup(page_source, 'html.parser')
    
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
                    logger.info(f"Found potential job title: {title_text}")
                    
                    # Try to find a URL near this title
                    nearby_link = card.find('a', href=True)
                    job_link = nearby_link['href'] if nearby_link else 'N/A'
                    
                    # Try to extract job ID from URL
                    job_id = 'N/A'
                    if job_link != 'N/A' and '/jobs/view/' in job_link:
                        try:
                            # Try regex to extract numeric ID
                            match = re.search(r'-(\d+)/?\?', job_link)
                            if match:
                                job_id = match.group(1)
                        except:
                            pass
                    
                    # Add this as a potential job
                    all_jobs.append({
                        'Job ID': job_id,
                        'Job Title': title_text,
                        'Company Name': 'unknown',
                        'Location': 'unknown',
                        'Job URL': job_link,
                        'job_description': 'N/A',
                        'seniority_level': 'N/A',
                        'employment_type': 'N/A',
                        'job_function': 'N/A',
                        'industries': 'N/A',
                        'applicants': 'N/A',
                        'date_posted': 'N/A'
                    })
                    break
                
        except Exception as e:
            logger.warning(f"Error in general approach: {e}")
            continue
    
    return all_jobs

def save_jobs_to_csv(processed_jobs, csv_filename):
    """Save processed jobs to a CSV file."""
    if processed_jobs:
        # Define all possible field names
        fieldnames = [
            'Job ID', 'Job Title', 'Company Name', 'Location', 'Job URL',
            'job_description', 'seniority_level', 'employment_type',
            'job_function', 'industries', 'applicants', 'date_posted'
        ]
        
        try:
            with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for job in processed_jobs:
                    writer.writerow(job)
            
            logger.info(f"Job details have been written to '{csv_filename}' successfully!")
            logger.info(f"Total jobs found: {len(processed_jobs)}")
            logger.info(f"Jobs with detailed information: {len([j for j in processed_jobs if j['job_description'] != 'N/A'])}")
        except Exception as e:
            logger.error(f"Error saving to CSV: {str(e)}")
    else:
        logger.warning("No jobs were found to write to CSV.")

def save_jobs_to_database(jobs, engine, jobs_table):
    """Save processed jobs to database, handling duplicates with Job ID as unique key."""
    if not jobs:
        logger.warning("No jobs to save to database")
        return
        
    # Add timestamp for when the data was scraped
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for job in jobs:
        job['date_scraped'] = current_time
        
    successful_inserts = 0
    successful_updates = 0
    failed_operations = 0
        
    logger.info(f"Saving {len(jobs)} jobs to database")
        
    try:
        with session_scope(engine) as session:
            for job in jobs:
                try:
                    # Skip jobs without a valid ID
                    if job['Job ID'] == 'N/A':
                        logger.warning("Skipping job without valid ID")
                        continue
                                        
                    # Check if job already exists in database
                    # FIX: Removed square brackets in select statement
                    stmt = select(jobs_table).where(jobs_table.c.job_id == job['Job ID'])
                    existing_job = session.execute(stmt).fetchone()
                                        
                    # Prepare data for database
                    job_data = {
                        'job_id': job['Job ID'],
                        'job_title': job['Job Title'],
                        'company_name': job['Company Name'],
                        'location': job['Location'],
                        'job_url': job['Job URL'],
                        'job_description': job['job_description'],
                        'seniority_level': job['seniority_level'],
                        'employment_type': job['employment_type'],
                        'job_function': job['job_function'],
                        'industries': job['industries'],
                        'applicants': job['applicants'],
                        'date_posted': job['date_posted'],
                        'date_scraped': job['date_scraped']
                    }
                                        
                    if existing_job:
                        # Update existing job
                        stmt = jobs_table.update().where(jobs_table.c.job_id == job['Job ID']).values(job_data)
                        session.execute(stmt)
                        successful_updates += 1
                    else:
                        # Insert new job
                        stmt = jobs_table.insert().values(job_data)
                        session.execute(stmt)
                        successful_inserts += 1
                                        
                except Exception as e:
                    logger.error(f"Error saving job ID {job.get('Job ID', 'unknown')} to database: {str(e)}")
                    failed_operations += 1
                    # Continue with the next job instead of failing the entire batch
                    continue
                
            logger.info(f"Database operation complete. Inserted: {successful_inserts}, Updated: {successful_updates}, Failed: {failed_operations}")
            
    except Exception as e:
        logger.error(f"Database transaction error: {str(e)}")
        logger.error(traceback.format_exc())

def scrape_linkedin_jobs_from_jobs_search(job_title=None, location=None, num_pages=None, use_xdotool=None, batch_size=5, max_workers=5):
    """
    Main function to scrape LinkedIn jobs with concurrent processing
    
    This function creates an asyncio event loop and runs the async scraping function
    """
    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        async_scrape_linkedin_jobs(
            job_title=job_title,
            location=location,
            num_pages=num_pages,
            use_xdotool=use_xdotool,
            batch_size=batch_size,
            max_workers=max_workers
        )
    )

