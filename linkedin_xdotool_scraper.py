import subprocess
import time
import webbrowser
import argparse
import csv
import os
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def open_linkedin_in_active_chrome(job_title, location):
    """
    Open LinkedIn jobs search in the active Chrome window
    
    Args:
        job_title (str): Job title to search for
        location (str): Location to search in
    """
    # Format the search URL
    search_url = f"https://www.linkedin.com/jobs/search/?keywords={job_title}&location={location}"
    
    try:
        # Get the active Chrome window
        chrome_window = subprocess.check_output(["xdotool", "search", "--onlyvisible", "--class", "google-chrome"]).strip().split()[0].decode('utf-8')
        
        # Activate the Chrome window
        subprocess.run(["xdotool", "windowactivate", chrome_window])
        
        # Give the window some time to focus
        time.sleep(1)
        
        # Open a new tab with Ctrl+T
        subprocess.run(["xdotool", "key", "--window", chrome_window, "ctrl+t"])
        
        # Give some time for the new tab to open
        time.sleep(1)
        
        # Type the URL and press Enter
        subprocess.run(["xdotool", "type", "--window", chrome_window, search_url])
        subprocess.run(["xdotool", "key", "--window", chrome_window, "Return"])
        
        # Return true to indicate success
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Error accessing Chrome window: {e}")
        # If Chrome is not running, open it with the given URL
        webbrowser.open(search_url)
        return False

def check_chrome_debugging_running(port=9222):
    """
    Check if Chrome is already running with debugging on specified port
    """
    try:
        # Find processes with --remote-debugging-port
        result = subprocess.run(
            ["pgrep", "-f", f"--remote-debugging-port={port}"],
            capture_output=True,
            text=True
        )
        return bool(result.stdout.strip())
    except Exception:
        return False

def start_chrome_debugging(port=9222):
    """
    Start a new Chrome instance with debugging enabled
    """
    try:
        # Only try to kill existing debugging session if one exists
        if check_chrome_debugging_running(port):
            try:
                subprocess.run(
                    ["pkill", "-f", f"--remote-debugging-port={port}"], 
                    check=False
                )
                time.sleep(2)
            except Exception as e:
                print(f"Warning: Failed to kill existing debugging session: {e}")
        
        # Start Chrome with debugging enabled
        subprocess.Popen([
            "google-chrome",
            f"--remote-debugging-port={port}",
            "--user-data-dir=/tmp/chrome-debug",
            "--no-first-run"
        ])
        
        # Give Chrome time to start
        time.sleep(5)
        return True
    except Exception as e:
        print(f"Error starting Chrome with debugging: {e}")
        return False

def scrape_linkedin_jobs(job_title, location, num_pages=1, use_xdotool=True):
    """
    Scrape LinkedIn jobs using a two-step approach:
    1. Use xdotool to open LinkedIn in the current Chrome window
    2. Use regular Selenium to scrape the data
    
    Args:
        job_title (str): Job title to search for
        location (str): Location to search in
        num_pages (int): Number of pages to scrape
        use_xdotool (bool): Whether to use xdotool to interact with Chrome
    """
    csv_filename = f"linkedin_jobs_{job_title.replace(' ', '_')}_{location.replace(' ', '_')}.csv"
    
    # Step 1: Open LinkedIn in the active Chrome window
    if use_xdotool:
        success = open_linkedin_in_active_chrome(job_title, location)
        if not success:
            print("Failed to open LinkedIn in active Chrome window")
            return
        
        # Give time for the page to load
        print("Waiting for LinkedIn to load...")
        time.sleep(10)
    
    # Step 2: Create a new Selenium instance to scrape the data
    # (We don't try to connect to the existing Chrome - that's causing the issues)
    options = Options()
    options.add_argument("--start-maximized")
    
    # Navigate to LinkedIn jobs search directly in this new browser
    driver = webdriver.Chrome(options=options)
    search_url = f"https://www.linkedin.com/jobs/search/?keywords={job_title}&location={location}"
    
    try:
        # Navigate to the search URL
        driver.get(search_url)
        
        # Use WebDriverWait for better reliability
        wait = WebDriverWait(driver, 30)
        
        # Wait for job listings to load
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'jobs-search__results-list')))
        
        all_jobs = []
        
        # Loop through the specified number of pages
        for page in range(num_pages):
            print(f"Scraping page {page + 1}...")
            
            # Wait for job listings to load
            time.sleep(3)
            
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
            
            # If there are more pages to scrape, click the next button
            if page < num_pages - 1:
                try:
                    # Find and click the next page button - try different selectors
                    next_button = None
                    for selector in [
                        "//button[@aria-label='Next']", 
                        "//button[contains(@aria-label, 'Page')]",
                        "//li[contains(@class, 'artdeco-pagination__indicator--number')]/button"
                    ]:
                        try:
                            buttons = driver.find_elements(By.XPATH, selector)
                            if buttons:
                                # Find the button with the next page number
                                current_page = page + 1
                                for button in buttons:
                                    if button.is_displayed() and button.is_enabled():
                                        if button.get_attribute("aria-label") == f"Page {current_page + 1}":
                                            next_button = button
                                            break
                            
                            if next_button:
                                break
                        except:
                            continue
                    
                    if next_button:
                        # Scroll to the button to make it clickable
                        driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                        time.sleep(1)
                        next_button.click()
                        
                        # Wait for the next page to load
                        time.sleep(3)
                    else:
                        print("Could not find next page button")
                        break
                except Exception as e:
                    print(f"Could not navigate to next page: {e}")
                    break
        
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Scrape LinkedIn Jobs using xdotool')
    parser.add_argument('--job_title', type=str, default='Python Developer', 
                        help='Job title to search for')
    parser.add_argument('--location', type=str, default='United States',
                        help='Location to search in')
    parser.add_argument('--pages', type=int, default=1,
                        help='Number of pages to scrape')
    parser.add_argument('--no_xdotool', action='store_true',
                        help='Disable using xdotool (use regular Selenium)')
    
    args = parser.parse_args()
    
    scrape_linkedin_jobs(
        job_title=args.job_title,
        location=args.location,
        num_pages=args.pages,
        use_xdotool=not args.no_xdotool
    )