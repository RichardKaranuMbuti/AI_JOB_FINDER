# Example resume data
resume_data = """
Richard Karanu
Nairobi, Kenya | Phone: +254701291911 | Email: officialforrichardk@gmail.com
LinkedIn | Github
Full Stack Software Engineer
Experienced Full Stack Software Engineer with 4+ years in Java,Typescript and Python ecosystems, specializing in
enterprise frameworks like React, Spring Boot,Node Js and Django. Possess strong skills in system architecture and
containerization that help technology companies deliver scalable, production-ready solutions. Demonstrated expertise in
modernizing applications through Docker while actively expanding knowledge in mobile development and Kubernetes.
Passionate about leveraging artificial intelligence and contributing to open-source projects that drive innovation.
TECHNICAL SKILLS
Proficient in: Python,Java,Typescript,SQL,Spring Boot, Django, React.js, Docker, AWS, Azure, NoSQL,Linux
Familiar with: Node.js,Microservices,Rest APIs,Kafka,Machine Learning & AI, Kubernetes, CI/CD ,GitHub Actions,Agile,
Swagger,Bash Scripting
Currently Learning: Go, React-Native, Agentic Computing
EXPERIENCE
Kreatoors AI (HR AI Advocacy)
Full Stack Software Engineer




Germany, Remote - Contract
Jan 2024 - Current
Architected and implemented secure multi-tenant API infrastructure using Node.js and Express, achieving 99.9%
uptime and reducing unauthorized access attempts
Optimized API performance through efficient MongoDB indexing and caching strategies, reducing average response
time from 800ms to 200ms while maintaining scalability
Led onboarding and mentoring of 3 new engineers while collaborating with CTO on feature implementations,
achieving 90% sprint completion rate
Established comprehensive API documentation and standardized coding practices, resulting in 60% faster
onboarding and 50% improvement in component reusability across the platform
Tech Stack: Node.js, TypeScript,Next.js, Express, MongoDB,,OpenAI API,AWS
Complasset (FinTech/Compliance)
Spain, Remote - Contract
Full Stack Software Engineer
Jun 2024 - Nov 2024
 Architected and led development of AI-powered compliance platform from concept to production, reducing document
review time by 20x for financial institutions
 Implemented Azure Cognitive Services pipeline with custom AI agents, processing 1,000+ pages daily with 95%
accuracy in MNPI detection, validated through user testing
 Engineered real-time news verification system using Perigon API, reducing false positives by 40% and improving
detection confidence by 60%
 Designed secure document handling system with end-to-end encryption, achieving SOC2 compliance requirements
and zero security incidents
 Established automated testing pipeline achieving 90% code coverage, resulting in zero critical bugs in production
deployment
Tech Skills: Python (Django, FastAPI), React,Typescript,NestJS. Langgraph, Azure Cognitive Services, PostgreSQL,
Docker, JWT Authentication, Perigon API, Azure Cloud Services,OpenAI API
Miksi AI (AI as a Service)
Zagreb, Croatia, Remote - Contract
Full Stack Software Engineer
Jun 2023 - Apr 2024
 Engineered secure backend services for AI agents using JWT authentication, achieving zero security incidents
across 100,000+ API requests over 6 months
 Designed and deployed automated CI/CD pipelines using GitHub Actions and Docker, reducing deployment time
from 45 minutes to 8 minutes with 100% deployment success rate
 Optimized cloud infrastructure by implementing automated scaling and resource cleanup, cutting monthly Azure
costs by 35% while maintaining 99.9% service uptime
 Led a cross-functional team of 3 (2 developers, 1 data scientist), achieving 85% sprint completion rate and reducing
bug reports by 40% through systematic code reviews
 Developed Miksi AI SDK (published on PyPI) that simplified BI integrations, reaching 200+ downloads and
maintaining zero critical bugs in production
 Created context-aware AI agents for business intelligence tasks, achieving 90% accuracy in SQL query generation
across 100+ test cases
Managed end-to-end project lifecycle using Jira and GitHub Issues, delivering 4 major releases with 95% client
satisfaction rating
 Spearheaded weekly knowledge-sharing sessions with the development team, resulting in 30% faster onboarding of
new team members and improved cross-team collaboration
 Mentored 2 junior developers in AI integration practices, leading to successful feature additions within project
timeline
Tech Skills: Python,Django, Azure, Langgraph, LangSmith,FastAPI Microservices, Github Actions,Celery,AzureOpenAI,
OpenAIAPI
Dowell Research (HR and CRM)
UK - Remote - Contract
Backend Engineer
Oct 2022 - May 2023
 Developed RESTful APIs and WebSocket connections handling 1,000+ concurrent users, reducing average
response time from 800ms to 200ms
 Optimized PostgreSQL database performance through strategic indexing, reducing query times by 60% for
endpoints handling 10,000+ daily requests
 Implemented JWT authentication system processing 50,000+ daily requests with zero reported security breaches
over 8 months
 Built real-time communication system using WebSockets and Django Channels, maintaining 99.9% uptime for
5,000+ simultaneous connections
 Created comprehensive API documentation using Swagger UI, decreasing integration support tickets by 70% month-
over-month
 Bridged communication gaps between remote development teams across three time zones, establishing a
documentation-first approach that reduced project clarification meetings by 50%
Tech Skills: Python, Django,Docker, Swagger UI,Channels,Celery,DjangoRestFramework, WebSockets, Redis, Daphne,
HTMX
Freelance
Remote - Freelance
Freelance Software Engineer
May 2020 – Aug 2022




Led end-to-end development of 8+ custom applications for diverse clients, maintaining 95% client satisfaction rate
and 100% on-time delivery across all projects
Architected and deployed scalable solutions using React, Node.js, and Python, reducing client operational costs and
improving process efficiency
Established autonomous project management framework, handling requirements gathering to deployment
independently while maintaining zero scope creep across 15+ projects
Implemented data-driven solutions through custom dashboards and analytics tools, enabling 3x faster decision-
making for clients and achieving 90% user adoption rate
EDUCATION
Jomo Kenyatta University of Technology
Bachelor of Science in Computer Technology
Juja, Kenya
CERTIFICATIONS
API Security
API Sec University
Docker
Linkdln Learning
Link
Nov 2024
Link
Nov 2024
LANGUAGES & INTERESTS
LANGUAGES
English C2
Swahili , Native
INTERESTS & HOBBIES
Deep Learning,Research in AI,Open Source, Soccer, Cycling,Swimming
"""

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