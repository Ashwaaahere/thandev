"""
RAG store interface and implementations
"""
import logging
import uuid
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union

from app.core.config import settings
from app.rag.embeddings import get_embedding_provider

logger = logging.getLogger(__name__)


def normalize_qdrant_id(raw: Any) -> Union[int, str]:
    """Normalize ID for Qdrant (accepts int or UUID string)"""
    # Qdrant accepts int or UUID string. Everything else -> convert.
    if isinstance(raw, int):
        return raw

    if isinstance(raw, str):
        # allow UUID strings as-is
        try:
            uuid.UUID(raw)
            return raw
        except Exception:
            # deterministic UUID from string so re-indexing is stable
            return str(uuid.uuid5(uuid.NAMESPACE_URL, raw))

    # fallback
    return str(uuid.uuid4())


class RagStore(ABC):
    """Abstract interface for RAG storage"""
    
    @abstractmethod
    async def upsert_documents(self, docs: List[Dict[str, Any]]) -> None:
        """Upsert documents into the RAG store"""
        pass
    
    @abstractmethod
    async def query(
        self,
        query_text: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """Query the RAG store"""
        pass
    
    async def initialize(self) -> None:
        """Initialize the RAG store (optional)"""
        pass


class QdrantRagStore(RagStore):
    """Qdrant-based RAG store implementation"""
    
    def __init__(self, url: str, collection: str):
        self.url = url
        self.collection = collection
        self._client = None
        self._embedding_provider = None
    
    async def initialize(self) -> None:
        """Initialize Qdrant client"""
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams
            
            logger.info(f"Connecting to Qdrant at {self.url}")
            self._client = QdrantClient(url=self.url)
            
            # Test connection
            collections = self._client.get_collections().collections
            logger.info(f"✅ Connected to Qdrant at {self.url}, found {len(collections)} collections")
            
            self._embedding_provider = get_embedding_provider()
            
            # Create collection if it doesn't exist
            if not any(c.name == self.collection for c in collections):
                # Get embedding dimension from provider
                # Default to 384 for all-MiniLM-L6-v2, 1536 for OpenAI
                test_embedding = await self._embedding_provider.embed(["test"])
                dimension = len(test_embedding[0])
                
                self._client.create_collection(
                    collection_name=self.collection,
                    vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
                )
                logger.info(f"Created Qdrant collection: {self.collection} (dimension: {dimension})")
            else:
                logger.info(f"Using existing Qdrant collection: {self.collection}")
        except ImportError:
            logger.warning("qdrant-client not installed, Qdrant RAG store unavailable")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant: {e}", exc_info=True)
            raise
    
    async def upsert_documents(self, docs: List[Dict[str, Any]]) -> None:
        """Upsert documents into Qdrant"""
        if not self._client:
            await self.initialize()
        
        if not docs:
            return
        
        try:
            from qdrant_client.models import PointStruct
            
            # Extract texts for embedding
            texts = []
            for doc in docs:
                # Combine title, description, and content for embedding
                text_parts = []
                if doc.get("title"):
                    text_parts.append(doc["title"])
                if doc.get("description"):
                    text_parts.append(doc["description"])
                if doc.get("content"):
                    text_parts.append(str(doc["content"]))
                texts.append(" ".join(text_parts) if text_parts else "")
            
            # Generate embeddings
            embeddings = await self._embedding_provider.embed(texts)
            
            # Prepare points for Qdrant
            points = []
            for i, doc in enumerate(docs):
                # Extract payload (metadata)
                payload = {
                    k: v for k, v in doc.items()
                    if k not in ("id", "title", "description", "content", "text")
                }
                # Add text fields to payload for filtering
                if doc.get("title"):
                    payload["title"] = doc["title"]
                if doc.get("description"):
                    payload["description"] = doc["description"]
                if doc.get("content"):
                    payload["content"] = str(doc["content"])[:1000]  # Truncate for payload
                
                points.append(
                    PointStruct(
                        id=normalize_qdrant_id(doc.get("id")),
                        vector=embeddings[i],
                        payload=payload
                    )
                )
            
            # Upsert to Qdrant
            logger.info(f"Upserting {len(points)} points to Qdrant collection={self.collection}")
            if points:
                logger.info(f"Example point id: {points[0].id}")
            
            self._client.upsert(
                collection_name=self.collection,
                points=points
            )
            
            logger.info(f"Upserted {len(docs)} documents to Qdrant collection {self.collection}")
        except Exception as e:
            logger.error(f"Failed to upsert documents to Qdrant: {e}", exc_info=True)
            raise
    
    async def query(
        self,
        query_text: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """Query Qdrant"""
        if not self._client:
            await self.initialize()
        
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue, Distance, VectorParams
            from qdrant_client.http.exceptions import UnexpectedResponse
            
            # Ensure collection exists - create if missing
            try:
                collections = self._client.get_collections().collections
                collection_exists = any(c.name == self.collection for c in collections)
                
                if not collection_exists:
                    logger.info(f"Collection {self.collection} does not exist, creating it...")
                    if not self._embedding_provider:
                        self._embedding_provider = get_embedding_provider()
                    # Get embedding dimension from provider
                    test_embedding = await self._embedding_provider.embed(["test"])
                    dimension = len(test_embedding[0])
                    
                    self._client.create_collection(
                        collection_name=self.collection,
                        vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
                    )
                    logger.info(f"Created Qdrant collection: {self.collection} (dimension: {dimension})")
            except Exception as e:
                logger.warning(f"Failed to ensure collection exists: {e}. Will attempt query anyway.")
            
            # Generate query embedding
            if not self._embedding_provider:
                self._embedding_provider = get_embedding_provider()
            query_embedding = await self._embedding_provider.embed([query_text])
            
            # Build filter if provided
            qdrant_filter = None
            if filters:
                conditions = []
                for key, value in filters.items():
                    if isinstance(value, (str, int, float, bool)):
                        conditions.append(
                            FieldCondition(key=key, match=MatchValue(value=value))
                        )
                    elif isinstance(value, list):
                        # Handle list filters (e.g., severity in ["high", "critical"])
                        for v in value:
                            conditions.append(
                                FieldCondition(key=key, match=MatchValue(value=v))
                            )
                
                if conditions:
                    qdrant_filter = Filter(must=conditions)
            
            # Search Qdrant using query_points
            # query_points accepts list[float] directly for nearest search (simplest approach)
            query_vector = query_embedding[0]  # list[float]
            
            results = self._client.query_points(
                collection_name=self.collection,
                query=query_vector,  # Pass vector directly as list[float]
                query_filter=qdrant_filter,
                limit=top_k,
                with_payload=True,
            )
            
            # Format results
            formatted_results = []
            # query_points returns a QueryResponse with points
            if hasattr(results, 'points'):
                for point in results.points:
                    formatted_results.append({
                        "id": str(point.id),
                        "score": getattr(point, 'score', 0.0),
                        "metadata": point.payload or {},
                    })
            else:
                # Fallback for different response format
                for result in results:
                    formatted_results.append({
                        "id": str(getattr(result, 'id', result)),
                        "score": getattr(result, 'score', 0.0),
                        "metadata": getattr(result, 'payload', {}) or {},
                    })
            
            logger.debug(f"Qdrant query returned {len(formatted_results)} results")
            return formatted_results
        except Exception as e:
            # Handle 404 (collection not found) gracefully - return empty results
            error_str = str(e)
            if "404" in error_str or "Not Found" in error_str or "not found" in error_str.lower():
                logger.debug(f"Qdrant collection {self.collection} not found, returning empty results")
                return []
            logger.error(f"Failed to query Qdrant: {e}", exc_info=True)
            return []


class PgVectorRagStore(RagStore):
    """PostgreSQL + pgvector RAG store implementation"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self._engine = None
        self._embedding_provider = None
    
    async def initialize(self) -> None:
        """Initialize PostgreSQL connection"""
        try:
            from sqlalchemy import create_engine, text
            
            self._engine = create_engine(self.database_url)
            self._embedding_provider = get_embedding_provider()
            
            # Check if pgvector extension exists
            with self._engine.connect() as conn:
                result = conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
                if result.fetchone() is None:
                    logger.warning("pgvector extension not found, creating...")
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                    conn.commit()
                
                # Create table if it doesn't exist
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS rag_documents (
                        id TEXT PRIMARY KEY,
                        title TEXT,
                        description TEXT,
                        content TEXT,
                        doc_type TEXT,
                        org_id TEXT,
                        project_id TEXT,
                        target TEXT,
                        tool_id TEXT,
                        severity TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        embedding vector(384)
                    )
                """))
                conn.commit()
                
                # Create indexes
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_rag_documents_org_project 
                    ON rag_documents(org_id, project_id)
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_rag_documents_doc_type 
                    ON rag_documents(doc_type)
                """))
                conn.commit()
            
            logger.info("PostgreSQL + pgvector initialized")
        except ImportError:
            logger.warning("sqlalchemy not installed, PgVector RAG store unavailable")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize PgVector: {e}", exc_info=True)
            raise
    
    async def upsert_documents(self, docs: List[Dict[str, Any]]) -> None:
        """Upsert documents into PostgreSQL"""
        if not self._engine:
            await self.initialize()
        
        if not docs:
            return
        
        try:
            from sqlalchemy import text
            
            # Extract texts for embedding
            texts = []
            for doc in docs:
                text_parts = []
                if doc.get("title"):
                    text_parts.append(doc["title"])
                if doc.get("description"):
                    text_parts.append(doc["description"])
                if doc.get("content"):
                    text_parts.append(str(doc["content"]))
                texts.append(" ".join(text_parts) if text_parts else "")
            
            # Generate embeddings
            embeddings = await self._embedding_provider.embed(texts)
            
            # Upsert documents
            with self._engine.connect() as conn:
                for i, doc in enumerate(docs):
                    doc_id = doc.get("id") or f"doc_{i}"
                    embedding_str = "[" + ",".join(map(str, embeddings[i])) + "]"
                    
                    conn.execute(text("""
                        INSERT INTO rag_documents (
                            id, title, description, content, doc_type,
                            org_id, project_id, target, tool_id, severity,
                            embedding
                        ) VALUES (
                            :id, :title, :description, :content, :doc_type,
                            :org_id, :project_id, :target, :tool_id, :severity,
                            :embedding::vector
                        )
                        ON CONFLICT (id) DO UPDATE SET
                            title = EXCLUDED.title,
                            description = EXCLUDED.description,
                            content = EXCLUDED.content,
                            doc_type = EXCLUDED.doc_type,
                            org_id = EXCLUDED.org_id,
                            project_id = EXCLUDED.project_id,
                            target = EXCLUDED.target,
                            tool_id = EXCLUDED.tool_id,
                            severity = EXCLUDED.severity,
                            embedding = EXCLUDED.embedding
                    """), {
                        "id": doc_id,
                        "title": doc.get("title"),
                        "description": doc.get("description"),
                        "content": str(doc.get("content", ""))[:10000],  # Truncate
                        "doc_type": doc.get("doc_type"),
                        "org_id": doc.get("org_id"),
                        "project_id": doc.get("project_id"),
                        "target": doc.get("target"),
                        "tool_id": doc.get("tool_id"),
                        "severity": doc.get("severity"),
                        "embedding": embedding_str,
                    })
                conn.commit()
            
            logger.info(f"Upserted {len(docs)} documents to PostgreSQL")
        except Exception as e:
            logger.error(f"Failed to upsert documents to PostgreSQL: {e}", exc_info=True)
            raise
    
    async def query(
        self,
        query_text: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """Query PostgreSQL + pgvector"""
        if not self._engine:
            await self.initialize()
        
        try:
            from sqlalchemy import text
            
            # Generate query embedding
            query_embedding = await self._embedding_provider.embed([query_text])
            embedding_str = "[" + ",".join(map(str, query_embedding[0])) + "]"
            
            # Build WHERE clause for filters
            where_clauses = []
            params = {"embedding": embedding_str, "top_k": top_k}
            
            if filters:
                for key, value in filters.items():
                    if isinstance(value, (str, int, float, bool)):
                        where_clauses.append(f"{key} = :{key}")
                        params[key] = value
                    elif isinstance(value, list):
                        where_clauses.append(f"{key} = ANY(:{key})")
                        params[key] = value
            
            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
            
            # Query with cosine similarity
            query_sql = f"""
                SELECT 
                    id, title, description, content, doc_type,
                    org_id, project_id, target, tool_id, severity, created_at,
                    1 - (embedding <=> :embedding::vector) as score
                FROM rag_documents
                WHERE {where_sql}
                ORDER BY embedding <=> :embedding::vector
                LIMIT :top_k
            """
            
            with self._engine.connect() as conn:
                result = conn.execute(text(query_sql), params)
                rows = result.fetchall()
                
                formatted_results = []
                for row in rows:
                    formatted_results.append({
                        "id": row[0],
                        "score": float(row[11]) if row[11] is not None else 0.0,
                        "metadata": {
                            "title": row[1],
                            "description": row[2],
                            "content": row[3],
                            "doc_type": row[4],
                            "org_id": row[5],
                            "project_id": row[6],
                            "target": row[7],
                            "tool_id": row[8],
                            "severity": row[9],
                            "created_at": row[10].isoformat() if row[10] else None,
                        }
                    })
                
                logger.debug(f"PostgreSQL query returned {len(formatted_results)} results")
                return formatted_results
        except Exception as e:
            logger.error(f"Failed to query PostgreSQL: {e}", exc_info=True)
            return []


def get_rag_store() -> RagStore:
    """Get the configured RAG store instance"""
    store_type = settings.RAG_STORE_TYPE.lower()
    
    if store_type == "qdrant":
        return QdrantRagStore(
            url=settings.QDRANT_URL,
            collection=settings.QDRANT_COLLECTION,
        )
    elif store_type == "pgvector":
        return PgVectorRagStore(database_url=settings.DATABASE_URL)
    else:
        raise ValueError(f"Unknown RAG store type: {store_type}")
