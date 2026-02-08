# AGENTS.md - Telegram Scraper Development Guide

This document provides guidelines for AI agents working on this Telegram scraper codebase.

## Project Overview

A Python-based Telegram channel scraper that fetches messages and media files. Built with Telethon, uses SQLite for storage, and provides CLI-based interaction.

## Commands

### Running the Application

```bash
# Main entry point
python main.py

# Alternative entry point
python telegram-scraper.py
```

### No Linting/Formatting Config

This project does not have formal linting or formatting tools configured. When making changes:

- Use 4 spaces for indentation
- Keep lines under 120 characters
- Follow existing code patterns (see below)

## Code Style Guidelines

### Imports

Organize imports in the following order with blank lines between groups:

```python
# Standard library imports
import asyncio
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Third-party imports
from telethon import TelegramClient
from telethon.errors import FloodWaitError

# Local application imports
from src.config import StateManager
from src.database import DatabaseManager
```

### Type Hints

Always use type hints for function signatures:

```python
# Good
async def scrape_channel(self, channel: str, offset_id: int) -> int:
    ...

def get_api_credentials(self) -> tuple:
    ...

# Avoid
async def scrape_channel(channel, offset_id):  # No type hints
    ...
```

Use `Optional` from typing for nullable values, not `| None` (Python 3.9+ compatible):

```python
# Good
def get_channel_name(self, channel_id: str) -> Optional[str]:
    return self.state.get("channel_names", {}).get(channel_id)

# Avoid
def get_channel_name(self, channel_id: str) -> str | None:  # Python 3.10+ syntax
    ...
```

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Classes | PascalCase | `ChannelScraper`, `StateManager` |
| Methods/Variables | snake_case | `get_api_credentials`, `batch_size` |
| Constants | UPPER_SNAKE_CASE | `MAX_CONCURRENT_DOWNLOADS` |
| Private Methods | _snake_case prefix | `_load_state`, `_migrate_database` |
| Module-level variables | snake_case | `state_file`, `batch_size` |

### Docstrings

Use Google-style docstrings for all public classes and methods:

```python
class ChannelScraper:
    """
    Channel scraper responsible for fetching messages from Telegram channels.

    Attributes:
        client: Telegram client instance
        db_manager: Database manager for persistence
        media_manager: Media download manager
        state_manager: State persistence manager
    """

    def __init__(
        self,
        client: TelegramClient,
        db_manager,
        media_manager,
        state_manager,
        batch_size: int = 100,
    ):
        """
        Initialize the channel scraper.

        Args:
            client: Telegram client instance
            db_manager: Database manager for persistence
            media_manager: Media download manager
            state_manager: State persistence manager
            batch_size: Number of messages to process in each batch
        """
        ...
```

### Class Structure

Follow this pattern for classes:

```python
class ClassName:
    """
    Brief description of the class.
    """

    def __init__(self, param1: Type, param2: Type = default):
        """
        Initialize the class.

        Args:
            param1: Description of param1
            param2: Description of param2 (default: default)
        """
        self.attribute = param1
        self._private_attribute = param2

    async def public_method(self, arg: Type) -> ReturnType:
        """
        Brief description of what the method does.

        Args:
            arg: Description of argument

        Returns:
            Description of return value
        """
        ...

    def _private_method(self) -> None:
        """
        Private method for internal use only.
        """
        ...
```

### Error Handling

Use specific exception types and provide meaningful error messages:

```python
# Good
try:
    with open(self.state_file, "r", encoding="utf-8") as f:
        return json.load(f)
except (json.JSONDecodeError, IOError) as e:
    print(f"Failed to load state: {e}")
    return default_state

# Avoid bare except
try:
    something()
except:  # Never do this
    pass
```

Handle async exceptions properly:

```python
async def safe_operation(self):
    """Perform operation with proper error handling."""
    try:
        result = await self.client.get_messages(entity)
        return result
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds)
        return await self.safe_operation()  # Retry
    except Exception as e:
        print(f"Operation failed: {e}")
        return None
```

### Async/Await Patterns

Use `async def` for blocking I/O operations and `asyncio` for concurrency:

```python
# Batch processing with progress tracking
async def scrape(self, channel: str, offset_id: int = 0) -> int:
    """Scrape messages from a channel with progress updates."""
    message_batch = []
    processed_count = 0

    async for message in self.client.iter_messages(entity, offset_id=offset_id):
        msg_data = self._parse_message(message)
        message_batch.append(msg_data)
        processed_count += 1

        # Batch insert for efficiency
        if len(message_batch) >= self.batch_size:
            self.db_manager.batch_insert_messages(channel, message_batch)
            message_batch.clear()

    # Final save
    if message_batch:
        self.db_manager.batch_insert_messages(channel, message_batch)

    return processed_count

# Concurrent downloads with semaphore
async def download_all(self, messages: List) -> int:
    """Download multiple files concurrently."""
    semaphore = asyncio.Semaphore(self.max_concurrent_downloads)

    async def download_with_semaphore(msg):
        async with semaphore:
            return await self.download_single(msg)

    tasks = [download_with_semaphore(msg) for msg in messages]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return sum(1 for r in results if r and not isinstance(r, Exception))
```

### Data Models

Use `@dataclass` for simple data structures:

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class MessageData:
    """Message data model for storing scraped content."""
    message_id: int
    date: str
    sender_id: int
    first_name: Optional[str]
    last_name: Optional[str]
    username: Optional[str]
    message: str
    media_type: Optional[str]
    media_path: Optional[str]
    reply_to: Optional[int]
    post_author: Optional[str]
    views: Optional[int]
    forwards: Optional[int]
    reactions: Optional[str]
```

### File Organization

Maintain the existing module structure:

```
src/
  __init__.py          # Package root with version and module docs
  config/              # State and configuration management
  database/            # SQLite operations and migrations
  auth/                # Telegram authentication
  media/               # Media downloading
  scraper/             # Message fetching logic
  export/              # CSV/JSON export functionality
  models/              # Data classes
  ui/                  # CLI menus and user interaction
```

### Database Patterns

Follow these patterns for database operations:

```python
class DatabaseManager:
    """Manages SQLite database connections and operations."""

    def __init__(self, batch_size: int = 100):
        self.db_connections: Dict[str, sqlite3.Connection] = {}
        self.batch_size = batch_size

    def _create_connection(self, channel: str) -> sqlite3.Connection:
        """Create a new database connection with optimizations."""
        channel_dir = Path(channel)
        channel_dir.mkdir(exist_ok=True)

        db_file = channel_dir / f"{channel}.db"
        conn = sqlite3.connect(str(db_file), check_same_thread=False)

        # Performance optimizations
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")

        # Create tables and indexes
        conn.execute(CREATE_TABLE_SQL)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_message_id ON messages(message_id)")

        return conn

    def _migrate_database(self, conn: sqlite3.Connection) -> None:
        """Add new columns for schema evolution."""
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(messages)")
        columns = {row[1] for row in cursor.fetchall()}

        migrations = []
        if "new_column" not in columns:
            migrations.append("ALTER TABLE messages ADD COLUMN new_column TEXT")

        for migration in migrations:
            try:
                conn.execute(migration)
            except sqlite3.OperationalError:
                pass

        if migrations:
            conn.commit()
```

## Working with Telegram API

### Client Initialization

```python
from telethon import TelegramClient

async def initialize_client(api_id: int, api_hash: str) -> TelegramClient:
    """Initialize and return an authenticated Telegram client."""
    client = TelegramClient("session", api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        await client.send_code_request(phone)
        code = input("Enter code: ")
        await client.sign_in(phone, code)

    return client
```

### Handling FloodWait

Always handle `FloodWaitError` gracefully:

```python
from telethon.errors import FloodWaitError

async def safe_request(coro_func):
    """Execute a coroutine with FloodWait handling."""
    try:
        return await coro_func()
    except FloodWaitError as e:
        print(f"Flood wait: sleeping for {e.seconds} seconds")
        await asyncio.sleep(e.seconds)
        return await safe_request(coro_func)  # Retry
```

## Commit Guidelines

When making commits, follow conventional commits:

```
feat: add continuous scraping mode
fix: handle missing media path in database
docs: update README with new usage examples
refactor: extract message parser into separate module
```

## Common Operations

### Adding a New Module

1. Create the module file in `src/<module_name>/__init__.py`
2. Export public classes in `src/<module_name>/__init__.py`
3. Import and use in `main.py` following existing patterns
4. Add docstrings in Chinese/English (project uses Chinese for user-facing text)

### Adding a Database Field

1. Add field to the dataclass model in `src/models/__init__.py`
2. Add column in database schema in `src/database/__init__.py`
3. Add migration logic in `_migrate_database()` method
4. Update relevant query operations

### Testing Changes

No formal test suite exists. Manual testing workflow:

1. Run the application: `python main.py`
2. Test authentication flow
3. Add a test channel
4. Verify message scraping
5. Check database persistence
6. Verify export functionality
