"""FastAPI application for the News Curation Agent."""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.agent import NewsAgent
from src.config import get_settings
from src.models.schemas import (
    JobStatus,
    ProcessedResult,
    ProcessingStatus,
    URLSubmitRequest,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory job storage (use Redis/Firestore in production)
jobs: Dict[str, JobStatus] = {}
jobs_lock = asyncio.Lock()

# Global agent instance
agent: Optional[NewsAgent] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    global agent
    logger.info("Starting News Curation Agent API...")
    agent = NewsAgent()
    yield
    logger.info("Shutting down News Curation Agent API...")
    if agent:
        await agent.close()


app = FastAPI(
    title="News Curation Agent API",
    description=(
        "Autonomous agent for extracting, fact-checking, and summarizing "
        "content from news articles, Twitter/X, and SEC filings."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/api/submit", response_model=JobStatus)
async def submit_urls(
    request: URLSubmitRequest,
    background_tasks: BackgroundTasks,
):
    """
    Submit URLs for processing.

    Returns a job ID that can be used to check progress and retrieve results.
    """
    job_id = str(uuid.uuid4())

    # Create job status
    job = JobStatus(
        job_id=job_id,
        status=ProcessingStatus.PENDING,
        total_urls=len(request.urls),
        created_at=datetime.now(timezone.utc),
    )
    async with jobs_lock:
        jobs[job_id] = job

    # Start background processing
    background_tasks.add_task(
        process_urls_background,
        job_id,
        request.urls,
        request.include_raw_text,
        request.skip_fact_check,
    )

    return job


async def process_urls_background(
    job_id: str,
    urls: list[str],
    include_raw_text: bool,
    skip_fact_check: bool,
):
    """Background task to process URLs."""
    global agent

    async with jobs_lock:
        if job_id not in jobs:
            return
        job = jobs[job_id]
        job.status = ProcessingStatus.EXTRACTING

    # Ensure agent is created once before the loop
    if agent is None:
        agent = NewsAgent()

    try:
        for url in urls:
            result = await agent.process(
                url,
                skip_fact_check=skip_fact_check,
                include_raw_text=include_raw_text,
            )

            async with jobs_lock:
                job.results.append(result)
                if result.status == ProcessingStatus.COMPLETED:
                    job.completed += 1
                else:
                    job.failed += 1

        async with jobs_lock:
            job.status = ProcessingStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)

    except Exception as e:
        logger.exception(f"Error processing job {job_id}")
        async with jobs_lock:
            job.status = ProcessingStatus.FAILED
            job.completed_at = datetime.now(timezone.utc)


@app.get("/api/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Get the status and results of a processing job."""
    async with jobs_lock:
        if job_id not in jobs:
            raise HTTPException(status_code=404, detail="Job not found")
        return jobs[job_id]


@app.get("/api/jobs/{job_id}/results", response_model=list[ProcessedResult])
async def get_job_results(job_id: str):
    """Get only the results of a completed job."""
    async with jobs_lock:
        if job_id not in jobs:
            raise HTTPException(status_code=404, detail="Job not found")
        return jobs[job_id].results


@app.post("/api/process", response_model=ProcessedResult)
async def process_single_url(
    url: str,
    skip_fact_check: bool = False,
    include_raw_text: bool = False,
):
    """
    Process a single URL synchronously.

    For quick processing of individual URLs without job tracking.
    """
    global agent

    if agent is None:
        agent = NewsAgent()

    try:
        result = await agent.process(
            url,
            skip_fact_check=skip_fact_check,
            include_raw_text=include_raw_text,
        )
        return result

    except Exception as e:
        logger.exception(f"Error processing URL: {url}")
        raise HTTPException(status_code=500, detail="Failed to process URL")


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its results."""
    async with jobs_lock:
        if job_id not in jobs:
            raise HTTPException(status_code=404, detail="Job not found")
        del jobs[job_id]
    return {"message": "Job deleted"}


@app.get("/api/jobs")
async def list_jobs(limit: int = 100, status: Optional[str] = None):
    """List all jobs with optional status filter."""
    async with jobs_lock:
        job_list = list(jobs.values())

    if status:
        try:
            status_filter = ProcessingStatus(status)
            job_list = [j for j in job_list if j.status == status_filter]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    # Sort by creation time (newest first)
    job_list.sort(key=lambda j: j.created_at, reverse=True)

    return job_list[:limit]


# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    # Let FastAPI handle HTTPException normally
    if isinstance(exc, HTTPException):
        raise exc
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
