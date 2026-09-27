-- Database schema for RANN Agent Authentication System
-- Run with: sqlite3 rann.db < schema.sql

-- Users table
CREATE TABLE IF NOT EXISTS users (
 id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
 email TEXT UNIQUE NOT NULL,
 username TEXT UNIQUE NOT NULL,
 display_name TEXT,
 password_hash TEXT NOT NULL,
 email_verified INTEGER DEFAULT 0,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 last_login_at TIMESTAMP,
 disabled_at TIMESTAMP,
 verification_token TEXT,
 verification_token_expires TIMESTAMP,
 reset_token TEXT,
 reset_token_expires TIMESTAMP
);

-- Sessions table
CREATE TABLE IF NOT EXISTS sessions (
 id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
 user_id TEXT NOT NULL,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 expires_at TIMESTAMP NOT NULL,
 revoked_at TIMESTAMP,
 ip_address TEXT,
 user_agent TEXT,
 FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Projects table
CREATE TABLE IF NOT EXISTS projects (
 id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
 owner_id TEXT NOT NULL,
 name TEXT NOT NULL,
 slug TEXT UNIQUE NOT NULL,
 description TEXT,
 workspace_id TEXT,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Agent Sessions table
CREATE TABLE IF NOT EXISTS agent_sessions (
 id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
 user_id TEXT NOT NULL,
 project_id TEXT NOT NULL,
 status TEXT DEFAULT 'pending',
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
 FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- Execution History table
CREATE TABLE IF NOT EXISTS execution_history (
 id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
 user_id TEXT NOT NULL,
 project_id TEXT NOT NULL,
 agent_session_id TEXT,
 command TEXT,
 output TEXT,
 started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 completed_at TIMESTAMP,
 status TEXT DEFAULT 'pending',
 FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
 FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
 FOREIGN KEY (agent_session_id) REFERENCES agent_sessions(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_projects_owner_id ON projects(owner_id);
CREATE INDEX IF NOT EXISTS idx_agent_sessions_user_id ON agent_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_sessions_project_id ON agent_sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_execution_history_user_id ON execution_history(user_id);
CREATE INDEX IF NOT EXISTS idx_execution_history_project_id ON execution_history(project_id);
