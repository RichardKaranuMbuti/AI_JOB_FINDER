import argparse
from scraper import scrape_linkedin_jobs_from_jobs_search
import config

def main():
    """
    Main function that parses command-line arguments and calls the scraper.
    If arguments are provided, they override config.py values.
    """
    parser = argparse.ArgumentParser(description='Scrape LinkedIn Jobs using xdotool')
    parser.add_argument('--job_title', type=str, 
                        help=f'Job title to search for (default: {config.JOB_TITLE})')
    parser.add_argument('--location', type=str, 
                        help=f'Location to search in (default: {config.LOCATION})')
    parser.add_argument('--pages', type=int, 
                        help=f'Number of pages to scrape (default: {config.NUM_PAGES})')
    parser.add_argument('--no_xdotool', action='store_true',
                        help='Disable using xdotool (use regular Selenium)')
    
    args = parser.parse_args()
    
    # Only use arguments if they were explicitly provided
    job_title = args.job_title if args.job_title is not None else None
    location = args.location if args.location is not None else None
    num_pages = args.pages if args.pages is not None else None
    use_xdotool = not args.no_xdotool if args.no_xdotool is not False else None
    

    scrape_linkedin_jobs_from_jobs_search(
        job_title=job_title,
        location=location,
        num_pages=num_pages,
        use_xdotool=use_xdotool
    )

if __name__ == "__main__":
    main()