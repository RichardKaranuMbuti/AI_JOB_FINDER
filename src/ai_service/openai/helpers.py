# def list_jobs_in_database():
#     """List all jobs in the database to verify data."""
#     engine, jobs_table, _ = init_database(config.DATABASE_URL)
    
#     with session_scope(engine) as session:
#         result = session.execute(select(jobs_table)).fetchall()
#         print(f"Found {len(result)} jobs in database")
        
#         if result:
#             for i, job in enumerate(result[:5]):  # Print first 5 for brevity
#                 print(f"Job {i+1}: ID={job.job_id}, Title={job.job_title}, Company={job.company_name}")
            
#             if len(result) > 5:
#                 print(f"... and {len(result) - 5} more jobs")

