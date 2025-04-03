import time
import csv
import re
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from chrome_setup import open_linkedin_in_active_chrome
import config
import concurrent.futures
from tqdm import tqdm


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
            
            # Extract number of applicants
            applicants_span = soup.find('span', class_='num-applicants__caption')
            if applicants_span:
                applicants_text = applicants_span.get_text(strip=True)
                # Extract only the number from "137 applicants"
                match = re.search(r'(\d+)', applicants_text)
                if match:
                    job_details['applicants'] = match.group(1)
            
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
    
    # Use provided parameters or fall back to config values
    job_title = job_title if job_title is not None else config.JOB_TITLE
    location = location if location is not None else config.LOCATION
    num_pages = num_pages if num_pages is not None else config.NUM_PAGES
    use_xdotool = use_xdotool if use_xdotool is not None else config.USE_XDOTOOL
    
    # Output information about the scraping job
    print(f"Starting LinkedIn job search (from Jobs menu) for '{job_title}' in '{location}'")
    print(f"Scraping {num_pages} page(s) with {max_workers} concurrent workers")
    
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
    options.add_argument("--disable-blink-features=AutomationControlled") 
    options.add_experimental_option("excludeSwitches", ["enable-automation"]) 
    options.add_experimental_option("useAutomationExtension", False) 
    
    # Navigate to LinkedIn jobs search directly in this new browser
    driver = webdriver.Chrome(options=options)
    
    all_jobs = []
    base_linkedin_url = "https://www.linkedin.com"
    
    try:
        # Create a progress bar for page scraping
        with tqdm(total=num_pages, desc="Scraping job listings pages") as pbar:
            # Loop through the specified number of pages
            for page in range(num_pages):
                # Calculate the start parameter for pagination
                start_param = 25 * page
                
                # Construct search URL with pagination parameter and encode spaces properly
                if page == 0:
                    search_url = f"https://www.linkedin.com/jobs/search/?keywords={job_title.replace(' ', '%20')}&location={location.replace(' ', '%20')}"
                else:
                    search_url = f"https://www.linkedin.com/jobs/search/?keywords={job_title.replace(' ', '%20')}&location={location.replace(' ', '%20')}&start={start_param}"
                
                print(f"\nNavigating to page {page + 1} with URL: {search_url}")
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
                        "ul.osvXwttVlxSToASQQxfDDAjwVGNfaCA"
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
                
                print(f"Found {len(job_cards)} job listings on page {page + 1}")
                
                # Create a progress bar for processing jobs on this page
                with tqdm(total=len(job_cards), desc=f"Processing jobs on page {page+1}") as job_pbar:
                    # Process job cards
                    for job_card in job_cards:
                        try:
                            # Extract job title - try multiple approaches
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
                            
                            # Extract job URL
                            job_link = 'N/A'
                            job_link_tag = job_card.find('a', href=lambda h: h and '/jobs/view/' in h)
                            
                            if job_link_tag:
                                job_link = job_link_tag.get('href')
                                # Ensure it's a full URL
                                if job_link and not job_link.startswith('http'):
                                    job_link = base_linkedin_url + job_link
                            
                            # Find company name
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
                            
                            # Find location
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
                            
                            # Extract job ID directly from the job card data-job-id attribute
                            job_id = 'N/A'
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
                                        print(f"Error extracting job ID from URL: {e}")
                            
                            # Create job entry
                            job_entry = {
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
                            
                            # Add job to our collection
                            all_jobs.append(job_entry)
                            job_pbar.update(1)
                            
                        except Exception as e:
                            print(f"Error processing job card: {e}")
                            job_pbar.update(1)
                            continue
                
                # Update the page progress bar
                pbar.update(1)
        
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
                    print(f"Error in general approach: {e}")
                    continue
        
        print(f"\nInitial job scraping complete. Found {len(all_jobs)} jobs.")
        print(f"Now fetching detailed information for jobs with valid Job IDs...")
        
        # Process all jobs to get detailed information
        processed_jobs = await process_all_jobs(all_jobs, location, batch_size=batch_size)
        
        # Write all collected jobs to CSV
        if processed_jobs:
            # Define all possible field names
            fieldnames = [
                'Job ID', 'Job Title', 'Company Name', 'Location', 'Job URL',
                'job_description', 'seniority_level', 'employment_type',
                'job_function', 'industries', 'applicants', 'date_posted'
            ]
            
            with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for job in processed_jobs:
                    writer.writerow(job)
            
            print(f"\nJob details have been written to '{csv_filename}' successfully!")
            print(f"Total jobs found: {len(processed_jobs)}")
            print(f"Jobs with detailed information: {len([j for j in processed_jobs if j['job_description'] != 'N/A'])}")
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


if __name__ == "__main__":
    # Example usage
    scrape_linkedin_jobs_from_jobs_search(
        job_title="AI Software Engineer",
        location="United States",
        num_pages=2,
        batch_size=5,
        max_workers=5
    )