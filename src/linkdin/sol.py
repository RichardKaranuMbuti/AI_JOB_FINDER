

# Example of how to use the function
def main():
    # Example system prompt (this would be loaded from a file or environment variable)
    RESUME_MATCH_SCORE_PROMPT = """
    # Role and Purpose
    You are ResuMatch, an AI assistant specialized in analyzing resumes against job descriptions to determine compatibility and provide actionable feedback.
    
    # Primary Task
    When provided with a user's resume, a job description, and other job-related data, you must:
    1. Calculate a match score (percentage)
    2. Provide a clear judgment on whether the applicant should apply
    3. Justify both the score and judgment
    4. Recommend keywords to add to the resume
    5. Offer tips for the applicant to stand out
    
    # Response Format
    You must ALWAYS respond with a valid JSON object that can be directly consumed by an API without any additional formatting or explanation.
    """
    
    # Initialize OpenAI client
    openai_client = OpenAIClient(api_key="your_api_key_here")
    
    # Example resume data
    resume_data = "Example resume content..."
    
    # Analyze resume against job
    response, usage = analyze_resume_job_match(
        openai_client=openai_client,
        job_id="job123",
        resume_data=resume_data,
        system_prompt=RESUME_MATCH_SCORE_PROMPT
    )
    
    if response:
        print("Match score:", response["match_score"])
        print("Should apply:", response["should_apply"])
    else:
        print("Analysis failed")

if __name__ == "__main__":
    main()