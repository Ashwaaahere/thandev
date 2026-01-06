"""
Embedding provider interface and implementations
"""
import logging
from abc import ABC, abstractmethod
from typing import List

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """Abstract interface for embedding providers"""
    
    @abstractmethod
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts"""
        pass


class SentenceTransformersProvider(EmbeddingProvider):
    """Sentence Transformers embedding provider"""
    
    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None
    
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using Sentence Transformers"""
        try:
            from sentence_transformers import SentenceTransformer
            
            if self._model is None:
                logger.info(f"Loading Sentence Transformers model: {self.model_name}")
                self._model = SentenceTransformer(self.model_name)
            
            # Generate embeddings
            embeddings = self._model.encode(texts, show_progress_bar=False)
            return embeddings.tolist()
        except ImportError:
            logger.error("sentence-transformers not installed")
            raise
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}", exc_info=True)
            raise


class OpenAIProvider(EmbeddingProvider):
    """OpenAI embedding provider"""
    
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
    
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using OpenAI API"""
        try:
            import openai
            
            if not self.api_key:
                raise ValueError("OpenAI API key not configured")
            
            client = openai.OpenAI(api_key=self.api_key)
            
            # OpenAI API call
            response = client.embeddings.create(
                model=self.model,
                input=texts,
            )
            
            return [item.embedding for item in response.data]
        except ImportError:
            logger.error("openai package not installed")
            raise
        except Exception as e:
            logger.error(f"Failed to generate OpenAI embeddings: {e}", exc_info=True)
            raise


def get_embedding_provider() -> EmbeddingProvider:
    """Get the configured embedding provider"""
    provider_type = settings.EMBEDDING_PROVIDER.lower()
    
    if provider_type == "sentence_transformers":
        return SentenceTransformersProvider(model_name=settings.EMBEDDING_MODEL)
    elif provider_type == "openai":
        if not settings.OPENAI_API_KEY:
            logger.warning("OpenAI API key not set, falling back to sentence_transformers")
            return SentenceTransformersProvider(model_name=settings.EMBEDDING_MODEL)
        return OpenAIProvider(
            api_key=settings.OPENAI_API_KEY,
            model=settings.OPENAI_EMBEDDING_MODEL,
        )
    else:
        raise ValueError(f"Unknown embedding provider: {provider_type}")




