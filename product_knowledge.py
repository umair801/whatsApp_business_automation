"""
Product Knowledge Base with Vector Embeddings for RAG
Enables intelligent product search and recommendations
"""

import os
import logging
from typing import List, Dict, Optional
from openai import OpenAI
import numpy as np
from supabase import Client


class ProductKnowledgeBase:
    """Manages product catalog with vector search capabilities"""
    
    def __init__(self, openai_client: OpenAI, supabase_client: Client):
        self.openai = openai_client
        self.supabase = supabase_client
        self.logger = logging.getLogger(__name__)
    
    def create_product_table(self):
        """Create products table in Supabase (run once)"""
        # This SQL should be run in Supabase SQL Editor
        sql = """
        -- Products table
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            brand TEXT,
            price DECIMAL(10, 2) NOT NULL,
            description TEXT,
            specifications JSONB,
            stock_quantity INTEGER DEFAULT 0,
            embedding vector(1536),
            created_at TIMESTAMP DEFAULT NOW()
        );
        
        -- Create index for vector similarity search
        CREATE INDEX IF NOT EXISTS products_embedding_idx 
        ON products USING ivfflat (embedding vector_cosine_ops);
        
        -- Create index for category search
        CREATE INDEX IF NOT EXISTS products_category_idx 
        ON products(category);
        """
        return sql
    
    def add_product(
        self,
        name: str,
        category: str,
        price: float,
        description: str,
        brand: Optional[str] = None,
        specifications: Optional[Dict] = None,
        stock_quantity: int = 0
    ) -> bool:
        """Add product with embedding to knowledge base"""
        try:
            # Generate embedding for product description
            embedding = self._generate_embedding(
                f"{name} {category} {brand or ''} {description}"
            )
            
            # Insert into database
            self.supabase.table('products').insert({
                "name": name,
                "category": category,
                "brand": brand,
                "price": price,
                "description": description,
                "specifications": specifications,
                "stock_quantity": stock_quantity,
                "embedding": embedding
            }).execute()
            
            self.logger.info(f"Product added: {name}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error adding product: {e}", exc_info=True)
            return False
    
    def search_products(
        self,
        query: str,
        category: Optional[str] = None,
        max_price: Optional[float] = None,
        limit: int = 5
    ) -> List[Dict]:
        """Search products using semantic similarity"""
        try:
            # Generate query embedding
            query_embedding = self._generate_embedding(query)
            
            # Build search query
            # Note: This requires pgvector extension in Supabase
            rpc_query = {
                "query_embedding": query_embedding,
                "match_threshold": 0.7,
                "match_count": limit
            }
            
            if category:
                rpc_query["category_filter"] = category
            if max_price:
                rpc_query["max_price"] = max_price
            
            # For now, use basic text search (upgrade to vector search after pgvector setup)
            products = self._text_search(query, category, max_price, limit)
            
            self.logger.info(
                f"Product search: query='{query}', results={len(products)}"
            )
            return products
        
        except Exception as e:
            self.logger.error(f"Search error: {e}", exc_info=True)
            return []
    
    def _text_search(
        self,
        query: str,
        category: Optional[str],
        max_price: Optional[float],
        limit: int
    ) -> List[Dict]:
        """Fallback text-based search"""
        try:
            # If category is provided, filter by category first
            if category:
                search_query = self.supabase.table('products').select('*')
                search_query = search_query.eq('category', category)
                if max_price:
                    search_query = search_query.lte('price', max_price)
                response = search_query.limit(limit).execute()
                return response.data
            
            # Otherwise search by query in name
            search_query = self.supabase.table('products').select('*')
            if max_price:
                search_query = search_query.lte('price', max_price)
            search_query = search_query.ilike('name', f'%{query}%')
            response = search_query.limit(limit).execute()
            
            # If no results in name, search description
            if not response.data:
                search_query = self.supabase.table('products').select('*')
                if max_price:
                    search_query = search_query.lte('price', max_price)
                search_query = search_query.ilike('description', f'%{query}%')
                response = search_query.limit(limit).execute()
            
            return response.data
        
        except Exception as e:
            self.logger.error(f"Text search error: {e}")
            return []
    
    def get_product_by_id(self, product_id: int) -> Optional[Dict]:
        """Get specific product details"""
        try:
            response = self.supabase.table('products') \
                .select('*') \
                .eq('id', product_id) \
                .single() \
                .execute()
            
            return response.data
        
        except Exception as e:
            self.logger.error(f"Error getting product: {e}")
            return None
    
    def get_products_by_category(
        self,
        category: str,
        limit: int = 10
    ) -> List[Dict]:
        """Get all products in a category"""
        try:
            response = self.supabase.table('products') \
                .select('*') \
                .eq('category', category) \
                .limit(limit) \
                .execute()
            
            return response.data
        
        except Exception as e:
            self.logger.error(f"Error getting category products: {e}")
            return []
    
    def format_product_response(
        self,
        products: List[Dict],
        language: str = "english"
    ) -> str:
        """Format products into user-friendly response"""
        if not products:
            responses = {
                "english": "Sorry, no products found matching your query.",
                "urdu": "معذرت، کوئی پروڈکٹ نہیں ملا۔",
                "roman_urdu": "Maazrat, koi product nahi mila."
            }
            return responses.get(language, responses["english"])
        
        # Format product list
        result = []
        for i, product in enumerate(products, 1):
            price = f"Rs. {product['price']:,.0f}"
            stock = "✅ In Stock" if product.get('stock_quantity', 0) > 0 else "❌ Out of Stock"
            
            result.append(
                f"{i}. **{product['name']}** (ID: {product['id']})\n"
                f"   💰 {price} | {stock}\n"
                f"   📝 {product.get('description', 'No description')[:80]}..."
            )
        
        header = {
            "english": f"Found {len(products)} products:\n\n",
            "urdu": f"{len(products)} پروڈکٹس ملے:\n\n",
            "roman_urdu": f"{len(products)} products milay:\n\n"
        }
                
        footer = {
            "english": "\n\n💡 To order, say: 'I want ID: X'",
            "roman_urdu": "\n\n💡 Order ke liye: 'Mujhe ID: X chahiye'"
        }

        return header.get(language, header["english"]) + "\n".join(result) + footer.get(language, "")

    def _generate_embedding(self, text: str) -> List[float]:
        """Generate OpenAI embedding for text"""
        try:
            response = self.openai.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            return response.data[0].embedding
        
        except Exception as e:
            self.logger.error(f"Embedding generation error: {e}")
            return [0.0] * 1536  # Return zero vector on error
    
    def update_stock(self, product_id: int, quantity: int) -> bool:
        """Update product stock quantity"""
        try:
            self.supabase.table('products') \
                .update({"stock_quantity": quantity}) \
                .eq('id', product_id) \
                .execute()
            
            self.logger.info(f"Stock updated: product_id={product_id}, qty={quantity}")
            return True
        
        except Exception as e:
            self.logger.error(f"Stock update error: {e}")
            return False