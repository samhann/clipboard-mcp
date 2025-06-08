"""
Clipboard monitoring module.
Polls clipboard for changes and processes new content.
"""

import asyncio
import base64
import logging
import hashlib
from typing import Optional, Dict, Any
from pathlib import Path
import json

import pyperclip
try:
    from PIL import Image, ImageGrab
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from .database import ClipboardDatabase
    from .url_fetcher import URLFetcher
except ImportError:
    from database import ClipboardDatabase
    from url_fetcher import URLFetcher

logger = logging.getLogger(__name__)

class ClipboardMonitor:
    """
    Monitors clipboard for changes and stores entries in database.
    """
    
    def __init__(self, db: ClipboardDatabase, poll_interval: float = 1.0):
        self.db = db
        self.poll_interval = poll_interval
        self.last_content_hash = None
        self.running = False
        self._monitor_task: Optional[asyncio.Task] = None
        
    def _calculate_hash(self, content: str) -> str:
        """Calculate hash of content for change detection."""
        return hashlib.md5(content.encode()).hexdigest()
        
    async def start(self):
        """Start monitoring clipboard."""
        if self.running:
            logger.warning("Monitor is already running")
            return
            
        self.running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Started clipboard monitoring (poll interval: {self.poll_interval}s)")
        
    async def stop(self):
        """Stop monitoring clipboard."""
        if not self.running:
            return
            
        self.running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
                
        logger.info("Stopped clipboard monitoring")
        
    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                await self._check_clipboard()
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(self.poll_interval)
                
    async def _check_clipboard(self):
        """Check clipboard for changes and process new content."""
        try:
            # Get text content
            text_content = pyperclip.paste()
            
            if text_content:
                content_hash = self._calculate_hash(text_content)
                
                if content_hash != self.last_content_hash:
                    self.last_content_hash = content_hash
                    await self._process_text_content(text_content)
                    
            # Check for image content (if PIL is available)
            if PIL_AVAILABLE:
                await self._check_image_clipboard()
                
        except Exception as e:
            logger.error(f"Error checking clipboard: {e}")
            
    async def _process_text_content(self, content: str):
        """Process new text content from clipboard."""
        logger.debug(f"Processing new clipboard content: {content[:50]}...")
        
        # Determine content type and extract URL if present
        url_fetcher = URLFetcher()
        is_url = url_fetcher.is_url(content)
        content_type = "url" if is_url else "text"
        
        # Add to database
        entry_id = await self.db.add_entry(
            content=content,
            content_type=content_type
        )
        
        # If it's a URL, fetch content asynchronously
        if is_url and entry_id:
            asyncio.create_task(self._fetch_url_content(entry_id, content, url_fetcher))
            
    async def _fetch_url_content(self, entry_id: int, url: str, url_fetcher: URLFetcher):
        """Fetch URL content asynchronously."""
        try:
            async with url_fetcher:
                # Extract clean URL if content has extra text
                clean_url = url_fetcher.extract_url(url)
                if not clean_url:
                    clean_url = url
                    
                result = await url_fetcher.fetch_url_content(clean_url)
                
                # Update database with fetched content
                await self.db.update_url_data(
                    entry_id=entry_id,
                    url_title=result.get("title"),
                    url_description=result.get("description"),
                    url_content=result.get("content"),
                    url_status_code=result.get("status_code"),
                    url_fetch_error=result.get("error")
                )
                
                if result.get("error"):
                    logger.warning(f"Failed to fetch URL {clean_url}: {result['error']}")
                else:
                    logger.info(f"Successfully fetched URL content for entry {entry_id}")
                    
        except Exception as e:
            logger.error(f"Error fetching URL content for entry {entry_id}: {e}")
            await self.db.update_url_data(
                entry_id=entry_id,
                url_fetch_error=f"Fetch error: {str(e)}"
            )
            
    async def _check_image_clipboard(self):
        """Check for image content in clipboard."""
        if not PIL_AVAILABLE:
            return
            
        try:
            # Try to get image from clipboard
            image = ImageGrab.grabclipboard()
            
            if image and isinstance(image, Image.Image):
                # Convert image to base64
                image_data = self._image_to_base64(image)
                image_format = image.format or "PNG"
                image_size = f"{image.width}x{image.height}"
                
                # Create a hash for the image data
                image_hash = hashlib.md5(image_data).hexdigest()
                content = f"[IMAGE:{image_hash}]"
                
                # Check if this image was already processed
                if hasattr(self, '_last_image_hash') and self._last_image_hash == image_hash:
                    return
                    
                self._last_image_hash = image_hash
                
                # Add to database
                await self.db.add_entry(
                    content=content,
                    content_type="image",
                    image_data=image_data,
                    image_format=image_format.lower(),
                    image_size=image_size
                )
                
                logger.info(f"Processed clipboard image: {image_size} {image_format}")
                
        except Exception as e:
            logger.debug(f"No image in clipboard or error: {e}")
            
    def _image_to_base64(self, image: Image.Image) -> bytes:
        """Convert PIL image to base64 bytes."""
        from io import BytesIO
        
        # Convert to RGB if needed (for JPEG compatibility)
        if image.mode in ('RGBA', 'LA', 'P'):
            # Create white background
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = background
            
        # Save to bytes
        buffer = BytesIO()
        image.save(buffer, format='PNG')
        image_bytes = buffer.getvalue()
        
        # Encode to base64
        return base64.b64encode(image_bytes)
        
    async def force_check(self):
        """Force a clipboard check (useful for testing)."""
        await self._check_clipboard()
        
    def get_status(self) -> Dict[str, Any]:
        """Get monitor status."""
        return {
            "running": self.running,
            "poll_interval": self.poll_interval,
            "last_content_hash": self.last_content_hash,
            "pil_available": PIL_AVAILABLE
        }