-- Clipboard History Database Schema
-- This schema stores clipboard entries with content, metadata, and fetched URL data

CREATE TABLE IF NOT EXISTS clipboard_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_hash TEXT UNIQUE NOT NULL,  -- SHA256 hash of content for deduplication
    content_type TEXT NOT NULL,         -- 'text', 'image', 'url', 'file'
    content TEXT,                       -- Raw clipboard content (text/url)
    content_preview TEXT,               -- First 200 chars for quick display
    image_data BLOB,                    -- Base64 encoded image data
    image_format TEXT,                  -- 'png', 'jpg', 'gif', etc.
    image_size TEXT,                    -- 'WxH' format
    is_url BOOLEAN DEFAULT FALSE,       -- Whether content is a detected URL
    url_title TEXT,                     -- Fetched page title
    url_description TEXT,               -- Meta description or excerpt
    url_content TEXT,                   -- Full fetched page content (text)
    url_status_code INTEGER,            -- HTTP status code
    url_fetch_error TEXT,               -- Error message if fetch failed
    source_app TEXT,                    -- Application that copied to clipboard (if available)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- Last time entry was queried
    access_count INTEGER DEFAULT 0     -- How many times entry was accessed
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_content_type ON clipboard_entries(content_type);
CREATE INDEX IF NOT EXISTS idx_created_at ON clipboard_entries(created_at);
CREATE INDEX IF NOT EXISTS idx_is_url ON clipboard_entries(is_url);
CREATE INDEX IF NOT EXISTS idx_content_hash ON clipboard_entries(content_hash);
CREATE INDEX IF NOT EXISTS idx_accessed_at ON clipboard_entries(accessed_at);