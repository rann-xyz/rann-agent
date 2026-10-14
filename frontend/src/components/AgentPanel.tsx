/**
 * Agent Panel Component - Real AI agent interface with backend integration
 */

import React, { useState, useRef, useEffect } from 'react';
import { cn } from '../lib/utils';

interface AgentPanelProps {
  projectId: string;
  className?: string;
}

interface AgentMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  tool_calls?: ToolCall[];
  isTool?: boolean;
}

interface ToolCall {
  id: string;
  name: string;
  arguments: Record<string, any>;
  result?: any;
  status: 'pending' | 'running' | 'completed' | 'failed';
}

interface WebSocketMessage {
  type: 'run_started' | 'run_completed' | 'run_failed' | 'run_cancelled' | 'agent_message' | 'agent_state';
  message?: string;
  run_id?: string;
  data?: string;
  error?: string;
  status?: string;
}

export function AgentPanel({ projectId, className }: AgentPanelProps): JSX.Element {
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Create agent session on mount
  useEffect(() => {
    const createSession = async () => {
      try {
        const response = await fetch(`/api/projects/${projectId}/agent/sessions`, {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
        });
        
        if (response.ok) {
          const data = await response.json();
          setSessionId(data.id);
        }
      } catch (err) {
        console.error('Failed to create agent session:', err);
      }
    };

    if (projectId) {
      createSession();
    }

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [projectId]);

  const connectWebSocket = () => {
    if (!sessionId || wsRef.current?.readyState === WebSocket.OPEN) return;

    const wsUrl = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/projects/${projectId}/agent/${sessionId}`;
    
    wsRef.current = new WebSocket(wsUrl);

    wsRef.current.onopen = () => {
      console.log('WebSocket connected');
    };

    wsRef.current.onmessage = (event) => {
      const msg: WebSocketMessage = JSON.parse(event.data);
      
      switch (msg.type) {
        case 'agent_message':
          if (msg.data) {
            setMessages(prev => {
              const newMsg: AgentMessage = {
                id: `${Date.now()}_${Math.random()}`,
                role: 'assistant',
                content: msg.data!,
                timestamp: new Date().toISOString(),
              };
              return [...prev, newMsg];
            });
          }
          break;
        case 'agent_state':
          if (msg.status) {
            // Could update status indicator here
            console.log('Agent state:', msg.status);
          }
          break;
        case 'run_completed':
          setIsStreaming(false);
          break;
        case 'run_failed':
          setIsStreaming(false);
          if (msg.error) {
            setMessages(prev => [...prev, {
              id: `${Date.now()}_error`,
              role: 'assistant',
              content: `Error: ${msg.error}`,
              timestamp: new Date().toISOString(),
            }]);
          }
          break;
        default:
          console.log('Unknown message type:', msg);
      }
    };

    wsRef.current.onclose = () => {
      console.log('WebSocket closed');
    };
  };

  const handleSend = () => {
    if (!input.trim()) return;

    const userMessage: AgentMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsStreaming(true);

    // Create new session if needed
    if (!sessionId) {
      createSession();
    }

    // Connect WebSocket
    connectWebSocket();

    // Send message via WebSocket
    setTimeout(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          type: 'message',
          message: input,
        }));
      } else {
        // Fallback to direct API call if WebSocket not available
        fetch(`/api/projects/${projectId}/agent/sessions`, {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: input }),
        })
          .then(res => res.json())
          .then(() => {
            setIsStreaming(false);
          })
          .catch(err => {
            console.error('Agent call failed:', err);
            setIsStreaming(false);
            setMessages(prev => [...prev, {
              id: `${Date.now()}_error`,
              role: 'assistant',
              content: 'Failed to connect to agent. Please try again.',
              timestamp: new Date().toISOString(),
            }]);
          });
      }
    }, 500);
  };

  // Create session helper
  const createSession = async () => {
    try {
      const response = await fetch(`/api/projects/${projectId}/agent/sessions`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      });
      
      if (response.ok) {
        const data = await response.json();
        setSessionId(data.id);
      }
    } catch (err) {
      console.error('Failed to create agent session:', err);
    }
  };

  return (
    <div className={cn("h-full flex flex-col", className)}>
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="space-y-4">
          {messages.map(message => (
            <div
              key={message.id}
              className={cn(
                "max-w-3/4 text-sm",
                message.role === 'user' 
                  ? 'ml-auto bg-blue-500/20 rounded-lg p-2' 
                  : 'mr-auto bg-gray-800/50 rounded-lg p-2'
              )}
            >
              <p className="text-gray-100">{message.content}</p>
              <span className="text-xs text-gray-500 ml-2">
                {new Date(message.timestamp).toLocaleTimeString()}
              </span>
            </div>
          ))}
          {isStreaming && (
            <div className="mr-auto bg-gray-800/50 rounded-lg p-2">
              <span className="animate-pulse">...</span>
            </div>
          )}
        </div>
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-gray-800">
        <div className="flex space-x-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Ask the agent..."
            className="flex-1 px-3 py-1 text-sm bg-gray-800 border border-gray-700 rounded focus:outline-none focus:border-blue-500"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isStreaming}
            className="px-3 py-1 text-sm text-white bg-blue-600 hover:bg-blue-500 rounded disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}