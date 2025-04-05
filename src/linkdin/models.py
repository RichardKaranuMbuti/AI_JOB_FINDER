from contextlib import contextmanager
from sqlalchemy import (Column, MetaData, String,Integer,DateTime, Table, Text, create_engine,
                       insert, select, update)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from src.linkdin.logging import setup_logging

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

    # Define the analyzed jobs table
    analyzed_jobs_table = Table(
        'analyzed_jobs',
        metadata,
        Column('job_id', String(50), primary_key=True),
        Column('match_score', Integer),
        Column('should_apply', String(5)),  # "true" or "false"
        Column('score_justification', Text),
        Column('judgment_justification', Text),
        Column('missing_keywords', Text),  # Stored as JSON string
        Column('improvement_tips', Text),  # Stored as JSON string
        Column('prompt_tokens', Integer),
        Column('completion_tokens', Integer),
        Column('total_tokens', Integer),
        Column('date_processed', DateTime)
    )
    
    # Create the tables if they don't exist
    metadata.create_all(engine)
    
    return engine, jobs_table, analyzed_jobs_table

# Session manager context
@contextmanager
def session_scope(engine):
    """Provide a transactional scope around a series of operations."""
    Session = sessionmaker(bind=engine)
    session = Session()
    print(session)
    try:
        yield session
        session.commit()
    except Exception as e:
        logger.error(f"Database session error: {e}")
        session.rollback()
        raise
    finally:
        session.close()