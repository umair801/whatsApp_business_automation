"""
Startup Validation Module
Runs on app boot to ensure environment and data are ready for production.
"""

import os
import logging

logger = logging.getLogger(__name__)

REQUIRED_ENV_VARS = [
    "OPENAI_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "JWT_SECRET",
]


def check_environment() -> None:
    """Validate all required environment variables are present.
    Raises EnvironmentError if any are missing.
    """
    missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]

    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}. "
            f"Set these in Railway Dashboard > Variables before deploying."
        )

    logger.info(f"Environment check passed | {len(REQUIRED_ENV_VARS)} variables verified")


def ensure_knowledge_base(product_kb) -> None:
    """Ensure ChromaDB has products indexed. Rebuilds from Supabase if empty.
    Handles Railway's ephemeral filesystem (cold start = empty ChromaDB).
    """
    try:
        # Check if any products are already indexed
        test_results = product_kb.search_products("laptop", limit=1)

        if test_results:
            logger.info(f"ChromaDB ready | products indexed")
            return

        # ChromaDB is empty -- rebuild from Supabase
        logger.warning("ChromaDB empty on startup -- rebuilding from Supabase...")

        response = product_kb.supabase.table("products").select("*").execute()
        products = response.data

        if not products:
            logger.warning("No products found in Supabase -- knowledge base will be empty")
            return

        rebuilt = 0
        for product in products:
            try:
                text = f"{product.get('name', '')} {product.get('category', '')} {product.get('brand', '')} {product.get('description', '')}"
                embedding = product_kb._generate_embedding(text)
                product_kb.supabase.table("products").update(
                    {"embedding": embedding}
                ).eq("id", product["id"]).execute()
                rebuilt += 1
            except Exception as e:
                logger.warning(f"Could not re-embed product {product.get('id')}: {e}")

        logger.info(f"ChromaDB rebuild complete | {rebuilt}/{len(products)} products re-indexed")

    except Exception as e:
        # Non-fatal: app can run without RAG (falls back to text search)
        logger.warning(f"Knowledge base check failed (non-fatal): {e}")
