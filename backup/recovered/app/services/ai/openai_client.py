"""
OpenAI client for AI-powered features
Provides a centralized wrapper around the OpenAI Python SDK
"""
import os
import logging
from typing import Optional
from openai import AsyncOpenAI
from openai import OpenAIError, APITimeoutError
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
# This ensures .env is loaded even when running in Celery workers
# Try to find .env in the backend directory (where this file is located)
backend_dir = Path(__file__).parent.parent.parent.parent  # Go up from app/services/ai/openai_client.py to backend/
env_path = backend_dir / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # Fallback to default behavior (searches from current working directory)
    load_dotenv()

logger = logging.getLogger(__name__)

# Initialize OpenAI client (singleton pattern)
_client: Optional[AsyncOpenAI] = None


def get_openai_client() -> AsyncOpenAI:
    """
    Get or create the OpenAI client instance.
    
    Returns:
        AsyncOpenAI client instance
        
    Raises:
        ValueError: If OPENAI_API_KEY is not set
    """
    global _client
    
    if _client is None:
        # Use Settings class which properly loads from .env via pydantic_settings
        from app.core.config import settings
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set. Please set it in backend/.env file.")
        
        _client = AsyncOpenAI(api_key=api_key)
        logger.info("Initialized OpenAI client")
    
    return _client


async def call_planner_llm(
    prompt: str,
    *,
    max_output_tokens: int = 800,
    model: str = "gpt-4o-mini",
    temperature: float = 0.3,
    timeout: float = 30.0,
) -> str:
    """
    Call the OpenAI API for planner LLM tasks.
    
    This function is designed for scan planning with strict token budgets:
    - Input: ≤ 4-6k tokens (enforced by prompt size limits)
    - Output: ≤ 1k tokens (controlled by max_output_tokens)
    
    Args:
        prompt: The prompt to send to the model
        max_output_tokens: Maximum tokens in response (default: 800, max: 1000)
        model: Model to use (default: "gpt-4o-mini", which is gpt-4.1-mini equivalent)
        temperature: Sampling temperature (default: 0.3 for deterministic planning)
        timeout: Request timeout in seconds (default: 30.0)
        
    Returns:
        The model's response text
        
    Raises:
        ValueError: If OPENAI_API_KEY is not set
        APITimeoutError: If the request times out
        OpenAIError: For other OpenAI API errors
    """
    # Validate max_output_tokens
    if max_output_tokens > 1000:
        logger.warning(f"max_output_tokens ({max_output_tokens}) exceeds recommended limit (1000), capping to 1000")
        max_output_tokens = 1000
    
    client = get_openai_client()
    
    logger.debug(
        f"Calling OpenAI planner LLM: model={model}, max_tokens={max_output_tokens}, "
        f"temperature={temperature}, timeout={timeout}s, prompt_length={len(prompt)}"
    )
    
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a security scan planning assistant. Analyze scan findings and recommend next tools to run. Output ONLY valid JSON, no markdown or explanations."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=max_output_tokens,
            temperature=temperature,
            timeout=timeout,
        )
        
        # Extract response text
        if not response.choices or not response.choices[0].message.content:
            raise ValueError("Empty response from OpenAI API")
        
        response_text = response.choices[0].message.content.strip()
        
        # Log token usage
        if response.usage:
            logger.info(
                f"OpenAI API usage: prompt_tokens={response.usage.prompt_tokens}, "
                f"completion_tokens={response.usage.completion_tokens}, "
                f"total_tokens={response.usage.total_tokens}"
            )
        
        return response_text
        
    except APITimeoutError as e:
        logger.error(f"OpenAI API timeout after {timeout}s: {e}")
        raise
    except OpenAIError as e:
        logger.error(f"OpenAI API error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error calling OpenAI API: {e}", exc_info=True)
        raise


