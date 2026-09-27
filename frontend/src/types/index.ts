/**
 * Type definitions for RANN Web IDE
 */

export interface Project {
  id: string;
  name: string;
  description?: string;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export interface TerminalSession {
  id: string;
  user_id: string;
  project_id: string;
  container_id: string;
  exec_id: string;
  status: 'creating' | 'created' | 'attached' | 'detached' | 'running' | 'closed' | 'failed';
  created_at: string;
  last_activity: string;
  cols: number;
  rows: number;
  websocket_active: boolean;
}

export interface FileNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  children?: FileNode[];
}

export interface FileContent {
  path: string;
  content: string;
  language: string;
}

export interface AgentMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  tool_calls?: ToolCall[];
}

export interface ToolCall {
  id: string;
  name: string;
  arguments: Record<string, any>;
  result?: any;
  status: 'pending' | 'running' | 'completed' | 'failed';
}

export interface WebSocketMessage {
  type: 'input' | 'output' | 'error' | 'exit' | 'ping' | 'pong' | 'resize' | 'status';
  data?: any;
  code?: string;
  message?: string;
  cols?: number;
  rows?: number;
}

export interface TerminalState {
  connected: boolean;
  sessionId: string | null;
  status: 'connecting' | 'connected' | 'disconnected' | 'reconnecting' | 'closed' | 'error';
  cols: number;
  rows: number;
}

export interface WorkspaceState {
  projectId: string;
  activeTerminalId: string | null;
  activeFile: string | null;
  unsavedFiles: Set<string>;
}