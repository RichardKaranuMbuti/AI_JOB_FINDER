

# Add this function to create a FastAPI endpoint
def create_fastapi_app():
    """Create FastAPI app with endpoints for scraping LinkedIn jobs."""
    from fastapi import FastAPI, BackgroundTasks, Query
    from pydantic import BaseModel
    
    app = FastAPI(title="LinkedIn Job Scraper API")
    
    class ScrapingParams(BaseModel):
        job_title: str = None
        location: str = None
        num_pages: int = None
        use_xdotool: bool = False
        batch_size: int = 5
        max_workers: int = 5
    
    @app.post("/scrape")
    async def scrape_jobs(params: ScrapingParams, background_tasks: BackgroundTasks):
        """Endpoint to start a LinkedIn job scraping task in the background."""
        background_tasks.add_task(
            async_scrape_linkedin_jobs,
            job_title=params.job_title,
            location=params.location,
            num_pages=params.num_pages,
            use_xdotool=params.use_xdotool,
            batch_size=params.batch_size,
            max_workers=params.max_workers
        )
        return {"status": "Job scraping task started in background"}
    
    @app.get("/jobs")
    async def get_jobs(
        job_title: str = Query(None, description="Filter by job title"),
        company: str = Query(None, description="Filter by company name"),
        location: str = Query(None, description="Filter by location")
    ):
        """Endpoint to retrieve scraped jobs with optional filters."""
        engine, jobs_table = init_database(config.DATABASE_URL)
        
        query = select([jobs_table])
        
        # Apply filters if provided
        if job_title:
            query = query.where(jobs_table.c.job_title.ilike(f"%{job_title}%"))
        if company:
            query = query.where(jobs_table.c.company_name.ilike(f"%{company}%"))
        if location:
            query = query.where(jobs_table.c.location.ilike(f"%{location}%"))
        
        with engine.connect() as connection:
            result = connection.execute(query)
            jobs = [dict(row) for row in result]
        
        return {"jobs": jobs, "count": len(jobs)}
    
    return app

"""
# To use the FastAPI app, create a new file named main.py with this content:

from your_module_name import create_fastapi_app

app = create_fastapi_app()

# Then run it with:
# uvicorn main:app --reload
"""