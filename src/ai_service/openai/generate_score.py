
import os
from dotenv import load_dotenv
from typing import Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import (select, insert )
import json
import datetime
from src.linkdin.models import init_database,session_scope
from src.linkdin import config
from src.ai_service.openai.openai_client import OpenAIClient
from src.linkdin.logging import setup_logging
from src.ai_service.openai.prompts import RESUME_MATCH_SCORE_PROMPT
from dotenv import load_dotenv

load_dotenv()

logger = setup_logging()

# Set your API key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = OpenAIClient(api_key=OPENAI_API_KEY)


# Pydantic model for validation
class JobMatchResponse(BaseModel):
    match_score: int = Field(..., ge=0, le=100)
    should_apply: bool
    score_justification: str
    judgment_justification: str
    missing_keywords: list[str]
    improvement_tips: list[str]


def get_job_data(session, jobs_table, job_id: str) -> Optional[Dict[str, Any]]:
    """ Retrieve job data from the database.
    Args:
        session: SQLAlchemy session
        jobs_table: SQLAlchemy table object
        job_id: ID of the job to retrieve
    Returns:
        Dictionary containing job data or None if not found
    """
    try:
        # Query the database for the job with the given ID
        stmt = select(jobs_table).where(jobs_table.c.job_id == job_id)
        result = session.execute(stmt).fetchone()
        print(f"result of get job: {result}")
        # Check if a result was found before converting to dictionary
        if result:
            # Convert the row to a dictionary
            job_data = {
                'job_id': result.job_id,
                'job_title': result.job_title,
                'company_name': result.company_name,
                'location': result.location,
                'job_url': result.job_url,
                'job_description': result.job_description,
                'seniority_level': result.seniority_level,
                'employment_type': result.employment_type,
                'job_function': result.job_function,
                'industries': result.industries,
                'applicants': result.applicants,
                'date_posted': result.date_posted,
                'date_scraped': result.date_scraped
            }
            return job_data
        else:
            return None
    except Exception as e:
        logger.error(f"Error retrieving job data for job ID {job_id}: {str(e)}")
        return None
    
def analyze_resume_job_match(
    openai_client: OpenAIClient,
    job_id: str,
    resume_data: str,
    system_prompt: str,
    max_retries: int = 2
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Analyze resume against job description using OpenAI API.
    
    Args:
        openai_client: Instance of OpenAIClient
        job_id: ID of the job to analyze
        resume_data: Resume text content
        system_prompt: System prompt for the OpenAI model
        max_retries: Maximum number of retries for API call
        
    Returns:
        Tuple of (validated response dict, token usage dict) or (None, None) if failed
    """
    # Initialize database and get job data
    engine, jobs_table, analyzed_jobs_table = init_database(config.DATABASE_URL)
    
    with session_scope(engine) as session:
        # Get job data from database
        job_data_dict = get_job_data(session, jobs_table, job_id)
        if not job_data_dict:
            return None, None
        
        # Extract required fields
        job_title = job_data_dict.get("job_title", "")
        job_description = job_data_dict.get("job_description", "")
        
        # Prepare additional job information as a formatted string
        additional_job_data = {
            "company_name": job_data_dict.get("company_name", ""),
            "location": job_data_dict.get("location", ""),
            "seniority_level": job_data_dict.get("seniority_level", ""),
            "employment_type": job_data_dict.get("employment_type", ""),
            "job_function": job_data_dict.get("job_function", ""),
            "industries": job_data_dict.get("industries", ""),
            "applicants": job_data_dict.get("applicants", ""),
            "date_posted": job_data_dict.get("date_posted", "")
        }
        
        # Convert additional job data to string format
        job_data_str = json.dumps(additional_job_data)
        
        # Prepare user content for OpenAI
        user_content = (
            f"Here is the resume data: {resume_data} and the job is titled: {job_title} "
            f"job description: {job_description}. Here is additional job information: {job_data_str}"
        )
        
        # Try API call with retries
        for attempt in range(max_retries):
            try:
                # Call OpenAI API
                response, usage = openai_client.create_chat_completion(
                    user_content=user_content,
                    system_prompt=system_prompt,
                    model="gpt-4o",
                    response_format={"type": "json_object"},
                    return_usage=True
                )
                
                # Parse JSON response
                response_dict = json.loads(response)
                
                # Validate response using Pydantic
                validated_response = JobMatchResponse(**response_dict)
                print(validated_response)
                
                # Save to database
                save_analysis_result(
                    session, 
                    analyzed_jobs_table,
                    job_id, 
                    validated_response.dict(),
                    usage
                )
                
                return response_dict, usage
                
            except ValidationError as e:
                logger.error(f"Response validation error (attempt {attempt+1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    logger.error("Maximum retries reached, giving up")
                    return None, None
            
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error (attempt {attempt+1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    logger.error("Maximum retries reached, giving up")
                    return None, None
            
            except Exception as e:
                logger.error(f"Unexpected error (attempt {attempt+1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    logger.error("Maximum retries reached, giving up")
                    return None, None

from datetime import datetime  # Add this import

def save_analysis_result(
    session,
    analyzed_jobs_table,
    job_id: str,
    response_data: Dict[str, Any],
    usage_data: Dict[str, Any]
):
    """
    Save analysis results to the database.
    
    Args:
        session: SQLAlchemy session
        analyzed_jobs_table: SQLAlchemy table for analyzed jobs
        job_id: Job ID
        response_data: Validated response from OpenAI
        usage_data: Token usage data
    """
    try:
        # Prepare data for insertion
        insert_data = {
            "job_id": job_id,
            "match_score": response_data["match_score"],
            "should_apply": str(response_data["should_apply"]).lower(),
            "score_justification": response_data["score_justification"],
            "judgment_justification": response_data["judgment_justification"],
            "missing_keywords": json.dumps(response_data["missing_keywords"]),
            "improvement_tips": json.dumps(response_data["improvement_tips"]),
            "prompt_tokens": usage_data.get("prompt_tokens", 0),
            "completion_tokens": usage_data.get("completion_tokens", 0),
            "total_tokens": usage_data.get("total_tokens", 0),
            "date_processed": datetime.now()
        }
        
        # Insert or update record
        query = select(analyzed_jobs_table).where(analyzed_jobs_table.c.job_id == job_id)
        existing_record = session.execute(query).fetchone()
        
        if existing_record:
            # Update existing record
            update_stmt = analyzed_jobs_table.update().where(
                analyzed_jobs_table.c.job_id == job_id
            ).values(**insert_data)
            session.execute(update_stmt)
        else:
            # Insert new record
            insert_stmt = insert(analyzed_jobs_table).values(**insert_data)
            session.execute(insert_stmt)
        
        logger.info(f"Successfully saved analysis for job ID: {job_id}")
        
    except Exception as e:
        logger.error(f"Error saving analysis result: {e}")
        raise


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

"""
    
# Analyze resume against job
def main_func():
    # list_jobs_in_database()
    response, usage = analyze_resume_job_match(
        openai_client=openai_client,
        job_id="4191815023",
        resume_data=resume_data,
        system_prompt=RESUME_MATCH_SCORE_PROMPT
    )


