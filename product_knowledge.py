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
    
    def add_product(self, name: str, category: str, price: float, description: str,
                    brand: Optional[str] = None, specifications: Optional[Dict] = None,
                    stock_quantity: int = 0) -> bool:
        try:
            embedding = self._generate_embedding(f"{name} {category} {brand or ''} {description}")
            self.supabase.table('products').insert({
                "name": name, "category": category, "brand": brand, "price": price,
                "description": description, "specifications": specifications,
                "stock_quantity": stock_quantity, "embedding": embedding
            }).execute()
            self.logger.info(f"Product added: {name}")
            return True
        except Exception as e:
            self.logger.error(f"Error adding product: {e}", exc_info=True)
            return False
    
    def search_products(self, query: str, category: Optional[str] = None,
                        max_price: Optional[float] = None, limit: int = 5) -> List[Dict]:
        try:
            products = self._text_search(query, category, max_price, limit)
            self.logger.info(f"Product search: query='{query}', results={len(products)}")
            return products
        except Exception as e:
            self.logger.error(f"Search error: {e}", exc_info=True)
            return []
    
    def _text_search(self, query: str, category: Optional[str],
                     max_price: Optional[float], limit: int) -> List[Dict]:
        try:
            if category:
                q = self.supabase.table('products').select('*').eq('category', category)
                if max_price:
                    q = q.lte('price', max_price)
                return q.limit(limit).execute().data
            
            q = self.supabase.table('products').select('*')
            if max_price:
                q = q.lte('price', max_price)
            result = q.ilike('name', f'%{query}%').limit(limit).execute().data
            
            if not result:
                q2 = self.supabase.table('products').select('*')
                if max_price:
                    q2 = q2.lte('price', max_price)
                result = q2.ilike('description', f'%{query}%').limit(limit).execute().data
            
            return result
        except Exception as e:
            self.logger.error(f"Text search error: {e}")
            return []
    
    def get_product_by_id(self, product_id: int) -> Optional[Dict]:
        try:
            return self.supabase.table('products').select('*').eq('id', product_id).single().execute().data
        except Exception as e:
            self.logger.error(f"Error getting product: {e}")
            return None
    
    def get_products_by_category(self, category: str, limit: int = 10) -> List[Dict]:
        try:
            return self.supabase.table('products').select('*').eq('category', category).limit(limit).execute().data
        except Exception as e:
            self.logger.error(f"Error getting category products: {e}")
            return []
    
    def format_product_response(self, products: List[Dict], language: str = "english") -> str:
        if not products:
            responses = {
                "english": "Sorry, no products found matching your query.",
                "urdu": "معذرت، کوئی پروڈکٹ نہیں ملا۔",
                "roman_urdu": "Maazrat, koi product nahi mila."
            }
            return responses.get(language, responses["english"])
        
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
        try:
            response = self.openai.embeddings.create(model="text-embedding-3-small", input=text)
            return response.data[0].embedding
        except Exception as e:
            self.logger.error(f"Embedding generation error: {e}")
            return [0.0] * 1536
    
    def update_stock(self, product_id: int, quantity: int) -> bool:
        try:
            self.supabase.table('products').update({"stock_quantity": quantity}).eq('id', product_id).execute()
            self.logger.info(f"Stock updated: product_id={product_id}, qty={quantity}")
            return True
        except Exception as e:
            self.logger.error(f"Stock update error: {e}")
            return False
