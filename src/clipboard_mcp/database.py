"""
Database module for clipboard history persistence.
Handles SQLite operations with async support.
"""

import asyncio
import hashlib
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import aiosqlite
import json

logger = logging.getLogger(__name__)


class ClipboardDatabase:
    """Async SQLite database for clipboard history."""
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            # Default to user's home directory
            home = Path.home()
            db_dir = home / ".clipboard-mcp"
            db_dir.mkdir(exist_ok=True)
            db_path = str(db_dir / "clipboard_history.db")
        
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None
        
    async def connect(self):
        """Connect to the database and initialize schema."""
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._initialize_schema()
        logger.info(f"Connected to clipboard database: {self.db_path}")
        
    async def close(self):
        """Close database connection."""
        if self._db:
            await self._db.close()
            self._db = None
            
    async def _initialize_schema(self):
        """Initialize database schema from SQL file."""
        schema_path = Path(__file__).parent / "schema.sql"
        
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
            
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
            
        # Execute schema in parts (SQLite doesn't like multiple statements)
        statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
        
        for statement in statements:
            try:
                await self._db.execute(statement)
            except Exception as e:
                logger.error(f"Error executing schema statement: {e}")
                logger.error(f"Statement: {statement[:100]}...")
                
        await self._db.commit()
        logger.info("Database schema initialized")
        
    def _calculate_content_hash(self, content: str, content_type: str) -> str:
        """Calculate SHA256 hash for content deduplication."""
        content_str = f"{content_type}:{content}"
        return hashlib.sha256(content_str.encode()).hexdigest()
        
    async def add_entry(
        self,
        content: str,
        content_type: str = "text",
        image_data: Optional[bytes] = None,
        image_format: Optional[str] = None,
        image_size: Optional[str] = None,
        source_app: Optional[str] = None
    ) -> Optional[int]:
        """
        Add a new clipboard entry to the database.
        Returns the entry ID if successful, None if duplicate.
        """
        content_hash = self._calculate_content_hash(content, content_type)
        content_preview = content[:200] if content else ""
        
        # Check if entry already exists
        existing = await self._db.execute(
            "SELECT id FROM clipboard_entries WHERE content_hash = ?",
            (content_hash,)
        )
        row = await existing.fetchone()
        if row:
            # Update access time for existing entry
            await self._db.execute(
                "UPDATE clipboard_entries SET accessed_at = CURRENT_TIMESTAMP, access_count = access_count + 1 WHERE id = ?",
                (row['id'],)
            )
            await self._db.commit()
            logger.debug(f"Updated existing entry {row['id']}")
            return row['id']
        
        # Insert new entry
        cursor = await self._db.execute("""
            INSERT INTO clipboard_entries (
                content_hash, content_type, content, content_preview,
                image_data, image_format, image_size, source_app
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            content_hash, content_type, content, content_preview,
            image_data, image_format, image_size, source_app
        ))
        
        await self._db.commit()
        entry_id = cursor.lastrowid
        logger.info(f"Added new clipboard entry {entry_id}: {content_type}")
        return entry_id
        
    async def update_url_data(
        self,
        entry_id: int,
        url_title: Optional[str] = None,
        url_description: Optional[str] = None,
        url_content: Optional[str] = None,
        url_status_code: Optional[int] = None,
        url_fetch_error: Optional[str] = None
    ):
        """Update URL-related data for an entry."""
        await self._db.execute("""
            UPDATE clipboard_entries 
            SET is_url = TRUE, url_title = ?, url_description = ?, 
                url_content = ?, url_status_code = ?, url_fetch_error = ?
            WHERE id = ?
        """, (url_title, url_description, url_content, url_status_code, url_fetch_error, entry_id))
        
        await self._db.commit()
        logger.debug(f"Updated URL data for entry {entry_id}")
        
    async def search_entries(
        self,
        query: Optional[str] = None,
        content_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        include_urls_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Search clipboard entries with optional filters.
        """
        params = []
        where_clauses = []
        
        if query:
            # Simple text search without FTS for now
            base_query = """
                SELECT * FROM clipboard_entries
                WHERE (content LIKE ? OR content_preview LIKE ? OR url_title LIKE ? OR url_description LIKE ?)
            """
            search_term = f"%{query}%"
            params.extend([search_term, search_term, search_term, search_term])
        else:
            base_query = "SELECT * FROM clipboard_entries"
            
        if content_type:
            where_clauses.append("content_type = ?")
            params.append(content_type)
            
        if include_urls_only:
            where_clauses.append("is_url = TRUE")
            
        if where_clauses:
            if query:
                base_query += " AND " + " AND ".join(where_clauses)
            else:
                base_query += " WHERE " + " AND ".join(where_clauses)
                
        # Add ordering and pagination
        base_query += " ORDER BY created_at DESC"
            
        base_query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor = await self._db.execute(base_query, params)
        rows = await cursor.fetchall()
        
        # Convert to dictionaries
        results = []
        for row in rows:
            entry = dict(row)
            # Don't include large binary data in search results
            if entry.get('image_data'):
                entry['has_image'] = True
                entry['image_data'] = None  # Remove binary data
            results.append(entry)
            
        logger.debug(f"Search returned {len(results)} entries")
        return results
        
    async def get_entry_by_id(self, entry_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific entry by ID."""
        cursor = await self._db.execute(
            "SELECT * FROM clipboard_entries WHERE id = ?",
            (entry_id,)
        )
        row = await cursor.fetchone()
        
        if row:
            # Update access tracking
            await self._db.execute(
                "UPDATE clipboard_entries SET accessed_at = CURRENT_TIMESTAMP, access_count = access_count + 1 WHERE id = ?",
                (entry_id,)
            )
            await self._db.commit()
            return dict(row)
            
        return None
        
    async def get_recent_entries(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get most recent clipboard entries."""
        return await self.search_entries(limit=limit)
        
    async def get_url_entries(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get entries that are URLs with fetched content."""
        return await self.search_entries(include_urls_only=True, limit=limit)
        
    async def delete_entry(self, entry_id: int) -> bool:
        """Delete an entry by ID."""
        cursor = await self._db.execute(
            "DELETE FROM clipboard_entries WHERE id = ?",
            (entry_id,)
        )
        await self._db.commit()
        
        success = cursor.rowcount > 0
        if success:
            logger.info(f"Deleted entry {entry_id}")
        return success
        
    async def cleanup_old_entries(self, days_old: int = 30, max_entries: int = 1000):
        """Clean up old entries to keep database size manageable."""
        # Delete entries older than specified days
        await self._db.execute("""
            DELETE FROM clipboard_entries 
            WHERE created_at < datetime('now', '-{} days')
        """.format(days_old))
        
        # Keep only the most recent max_entries
        await self._db.execute("""
            DELETE FROM clipboard_entries 
            WHERE id NOT IN (
                SELECT id FROM clipboard_entries 
                ORDER BY created_at DESC 
                LIMIT ?
            )
        """, (max_entries,))
        
        await self._db.commit()
        logger.info(f"Cleaned up old entries (>{days_old} days, keep latest {max_entries})")
        
    async def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        stats = {}
        
        # Total entries
        cursor = await self._db.execute("SELECT COUNT(*) as total FROM clipboard_entries")
        row = await cursor.fetchone()
        stats['total_entries'] = row['total']
        
        # Entries by type
        cursor = await self._db.execute("""
            SELECT content_type, COUNT(*) as count 
            FROM clipboard_entries 
            GROUP BY content_type
        """)
        rows = await cursor.fetchall()
        stats['entries_by_type'] = {row['content_type']: row['count'] for row in rows}
        
        # URL entries
        cursor = await self._db.execute("SELECT COUNT(*) as count FROM clipboard_entries WHERE is_url = TRUE")
        row = await cursor.fetchone()
        stats['url_entries'] = row['count']
        
        # Recent activity (last 24 hours)
        cursor = await self._db.execute("""
            SELECT COUNT(*) as count 
            FROM clipboard_entries 
            WHERE created_at > datetime('now', '-1 day')
        """)
        row = await cursor.fetchone()
        stats['entries_last_24h'] = row['count']
        
        return stats