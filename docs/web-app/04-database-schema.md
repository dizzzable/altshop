> [!WARNING]
> Исторический документ. Этот файл не входит в канонический комплект документации и не переаудировался в текущем проходе. Актуальная точка входа: [docs/README.md](../README.md)

# AltShop Web Application - Database Schema

## Overview

This document defines the database schema extensions for the web application. The core database schema remains unchanged; we're only adding tables for web session management.

---

## New Tables

### web_sessions

Stores active web sessions for authenticated users.

```sql
CREATE TABLE web_sessions (
    id SERIAL PRIMARY KEY,
    user_telegram_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    session_token VARCHAR(255) NOT NULL UNIQUE,
    refresh_token_hash VARCHAR(255) NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_active_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_web_sessions_token ON web_sessions(session_token);
CREATE INDEX idx_web_sessions_user ON web_sessions(user_telegram_id);
CREATE INDEX idx_web_sessions_expires ON web_sessions(expires_at);
```

**Columns:**

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL | Primary key |
| `user_telegram_id` | BIGINT | Telegram user ID (FK to users) |
| `session_token` | VARCHAR(255) | JWT access token hash |
| `refresh_token_hash` | VARCHAR(255) | Hashed refresh token |
| `ip_address` | VARCHAR(45) | User's IP address (IPv4/IPv6) |
| `user_agent` | TEXT | Browser user agent |
| `created_at` | TIMESTAMP | Session creation time |
| `expires_at` | TIMESTAMP | Session expiration time |
| `last_active_at` | TIMESTAMP | Last activity timestamp |

---

### web_auth_tokens

Token blacklist for revoked/expired tokens.

```sql
CREATE TABLE web_auth_tokens (
    id SERIAL PRIMARY KEY,
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Index
CREATE INDEX idx_web_auth_tokens_hash ON web_auth_tokens(token_hash);
CREATE INDEX idx_web_auth_tokens_expires ON web_auth_tokens(expires_at);
```

**Columns:**

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL | Primary key |
| `token_hash` | VARCHAR(255) | Hashed JWT token |
| `expires_at` | TIMESTAMP | Token expiration time |
| `created_at` | TIMESTAMP | Blacklist creation time |

---

## Entity Relationship

```
┌─────────────────────┐
│       users         │
│─────────────────────│
│ telegram_id (PK)    │◄────┐
│ username            │     │
│ name                │     │
│ ...                 │     │
└─────────────────────┘     │
                            │ 1
                            │
                            │
                            │ N
┌─────────────────────┐     │
│   web_sessions      │─────┘
│─────────────────────│
│ id (PK)             │
│ user_telegram_id (FK)
│ session_token       │
│ refresh_token_hash  │
│ ip_address          │
│ user_agent          │
│ created_at          │
│ expires_at          │
│ last_active_at      │
└─────────────────────┘
```

---

## Migration File

**File:** `src/infrastructure/database/migrations/versions/0028_add_web_sessions.py`

```python
"""add web sessions

Revision ID: 0028
Revises: 0027
Create Date: 2026-02-18

"""
from alembic import op
import sqlalchemy as sa

revision = '0028'
down_revision = '0027'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Web sessions table
    op.create_table(
        'web_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_telegram_id', sa.BigInteger(), nullable=False),
        sa.Column('session_token', sa.String(length=255), nullable=False),
        sa.Column('refresh_token_hash', sa.String(length=255), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, 
                  server_default=sa.func.now()),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('last_active_at', sa.TIMESTAMP(timezone=True), nullable=False, 
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_telegram_id'], ['users.telegram_id'], 
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_token')
    )
    
    # Create indexes
    op.create_index('idx_web_sessions_token', 'web_sessions', ['session_token'])
    op.create_index('idx_web_sessions_user', 'web_sessions', ['user_telegram_id'])
    op.create_index('idx_web_sessions_expires', 'web_sessions', ['expires_at'])
    
    # Token blacklist table
    op.create_table(
        'web_auth_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, 
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash')
    )
    
    op.create_index('idx_web_auth_tokens_hash', 'web_auth_tokens', ['token_hash'])
    op.create_index('idx_web_auth_tokens_expires', 'web_auth_tokens', ['expires_at'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_web_auth_tokens_expires', 'web_auth_tokens')
    op.drop_index('idx_web_auth_tokens_hash', 'web_auth_tokens')
    op.drop_index('idx_web_sessions_expires', 'web_sessions')
    op.drop_index('idx_web_sessions_user', 'web_sessions')
    op.drop_index('idx_web_sessions_token', 'web_sessions')
    
    # Drop tables
    op.drop_table('web_auth_tokens')
    op.drop_table('web_sessions')
```

---

## SQLAlchemy Models

### WebSession Model

**File:** `src/infrastructure/database/models/sql/web_session.py`

```python
from datetime import datetime, timedelta
from sqlalchemy import String, Text, BigInteger, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.utils.time import datetime_now
from .base import BaseSql


class WebSession(BaseSql):
    __tablename__ = "web_sessions"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_telegram_id: Mapped[int] = mapped_column(
        BigInteger, 
        ForeignKey("users.telegram_id", ondelete="CASCADE"),
        nullable=False
    )
    session_token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        server_default=func.now()
    )
    
    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="web_sessions",
        foreign_keys=[user_telegram_id]
    )
    
    @classmethod
    def create_session(cls, user_telegram_id: int, session_token: str, 
                       refresh_token: str, ip_address: str | None = None,
                       user_agent: str | None = None,
                       expires_in_days: int = 7) -> "WebSession":
        """Create a new web session"""
        import hashlib
        return cls(
            user_telegram_id=user_telegram_id,
            session_token=session_token,
            refresh_token_hash=hashlib.sha256(refresh_token.encode()).hexdigest(),
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=datetime_now() + timedelta(days=expires_in_days)
        )
    
    def is_expired(self) -> bool:
        """Check if session is expired"""
        return datetime_now() > self.expires_at
    
    def update_activity(self) -> None:
        """Update last activity timestamp"""
        self.last_active_at = datetime_now()
```

### WebAuthToken Model

**File:** `src/infrastructure/database/models/sql/web_auth_token.py`

```python
from datetime import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from src.core.utils.time import datetime_now
from .base import BaseSql


class WebAuthToken(BaseSql):
    __tablename__ = "web_auth_tokens"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        server_default=func.now()
    )
    
    @classmethod
    def blacklist_token(cls, token_hash: str, expires_at: datetime) -> "WebAuthToken":
        """Add token to blacklist"""
        return cls(
            token_hash=token_hash,
            expires_at=expires_at
        )
    
    def is_expired(self) -> bool:
        """Check if blacklist entry is expired"""
        return datetime_now() > self.expires_at
```

### User Model Extension

**File:** `src/infrastructure/database/models/sql/user.py` (add relationship)

```python
# Add to existing User model
web_sessions: Mapped[list["WebSession"]] = relationship(
    "WebSession",
    back_populates="user",
    foreign_keys="WebSession.user_telegram_id",
    lazy="selectin"
)
```

---

## Repository

**File:** `src/infrastructure/database/repositories/web_session.py`

```python
from datetime import datetime
from typing import Optional
from sqlalchemy import select, delete
from src.infrastructure.database.models.sql import WebSession, WebAuthToken
from .base import BaseRepository


class WebSessionRepository(BaseRepository):
    """Repository for web session management"""
    
    async def create(self, session: WebSession) -> WebSession:
        """Create new session"""
        return await self._create(session)
    
    async def get_by_token(self, token: str) -> Optional[WebSession]:
        """Get session by token"""
        return await self._get_one(WebSession, WebSession.session_token == token)
    
    async def get_user_sessions(self, user_telegram_id: int) -> list[WebSession]:
        """Get all sessions for user"""
        return await self._get_many(
            WebSession, 
            WebSession.user_telegram_id == user_telegram_id
        )
    
    async def update_activity(self, session_id: int) -> bool:
        """Update session last activity"""
        result = await self.session.execute(
            update(WebSession)
            .where(WebSession.id == session_id)
            .values(last_active_at=datetime.utcnow())
        )
        await self.session.commit()
        return result.rowcount > 0
    
    async def delete_session(self, session_id: int) -> bool:
        """Delete session"""
        return await self._delete(WebSession, WebSession.id == session_id)
    
    async def delete_user_sessions(self, user_telegram_id: int) -> int:
        """Delete all user sessions (logout all)"""
        result = await self.session.execute(
            delete(WebSession).where(WebSession.user_telegram_id == user_telegram_id)
        )
        await self.session.commit()
        return result.rowcount
    
    async def cleanup_expired(self) -> int:
        """Remove expired sessions"""
        result = await self.session.execute(
            delete(WebSession).where(WebSession.expires_at < datetime.utcnow())
        )
        await self.session.commit()
        return result.rowcount
    
    # Token blacklist
    async def blacklist_token(self, token_hash: str, expires_at: datetime) -> WebAuthToken:
        """Add token to blacklist"""
        token = WebAuthToken.blacklist_token(token_hash, expires_at)
        return await self._create(token)
    
    async def is_token_blacklisted(self, token_hash: str) -> bool:
        """Check if token is blacklisted"""
        result = await self.session.execute(
            select(WebAuthToken).where(
                WebAuthToken.token_hash == token_hash,
                WebAuthToken.expires_at > datetime.utcnow()
            )
        )
        return result.scalar_one_or_none() is not None
    
    async def cleanup_blacklist(self) -> int:
        """Remove expired blacklist entries"""
        result = await self.session.execute(
            delete(WebAuthToken).where(WebAuthToken.expires_at < datetime.utcnow())
        )
        await self.session.commit()
        return result.rowcount
```

---

## Session Management Flow

```
1. User authenticates via Telegram
   │
   ▼
2. Backend creates JWT tokens
   │
   ▼
3. Create WebSession record
   - Store session_token
   - Store refresh_token_hash
   - Store IP, user agent
   │
   ▼
4. Return tokens to client (httpOnly cookies)
   │
   ▼
5. Client includes tokens in all requests
   │
   ▼
6. Middleware validates token
   - Check signature
   - Check expiration
   - Check blacklist
   - Check session exists
   │
   ▼
7. Update last_active_at on successful request
   │
   ▼
8. On logout:
   - Add token to blacklist
   - Delete session record
```

---

## Cleanup Jobs

Add to existing Taskiq scheduler:

**File:** `src/infrastructure/taskiq/tasks/web.py`

```python
from src.infrastructure.database.repositories import WebSessionRepository
from src.infrastructure.taskiq.broker import broker

@broker.task(schedule=[{"cron": "0 3 * * *"}])  # Daily at 03:00
async def cleanup_web_sessions():
    """Clean up expired sessions and blacklist entries"""
    async with UnitOfWork() as uow:
        repo = WebSessionRepository(uow.session)
        
        # Clean expired sessions
        sessions_deleted = await repo.cleanup_expired()
        
        # Clean expired blacklist entries
        blacklist_deleted = await repo.cleanup_blacklist()
        
        logger.info(
            f"Cleaned up {sessions_deleted} expired sessions "
            f"and {blacklist_deleted} blacklist entries"
        )
```

---

## Security Considerations

1. **Token Storage**: Store hashed tokens, not plain text
2. **HTTPS Only**: All web traffic must use HTTPS
3. **httpOnly Cookies**: Tokens stored in httpOnly cookies (not localStorage)
4. **Session Expiration**: Sessions expire after 7 days by default
5. **IP Tracking**: Log IP addresses for security monitoring
6. **Rate Limiting**: Implement rate limiting on auth endpoints
7. **CSRF Protection**: Implement CSRF tokens for state-changing operations

---

## Next Steps

1. **Create migration file** and apply to database
2. **Implement WebSession model** and repository
3. **Add session middleware** for token validation
4. **Implement cleanup task** in Taskiq scheduler
5. **Test session management** (create, validate, delete)
6. **Monitor session metrics** (active sessions, expiration rate)
