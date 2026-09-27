/**
 * Agent Panel Component - AI agent interface
 */

import React, { useState } from 'react';
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
}

// Mock messages - will connect to real agent API
const mockMessages: AgentMessage[] = [
  {
    id: '1',
    role: 'system',
    content: 'Agent: Claude 3.5 Sonnet',
    timestamp: new Date().toISOString(),
  },
  {
    id: '2',
    role: 'user',
    content: 'Hello! I want to build a landing page.',
    timestamp: new Date().toISOString(),
  },
  {
    id: '3',
    role: 'assistant',
    content: 'I\'ll help you build a landing page. What style would you prefer? Modern, corporate, creative, or something else?',
    timestamp: new Date().toISOString(),
  },
];

export function AgentPanel({ projectId, className }: AgentPanelProps): JSX.Element {
  const [messages, setMessages] = useState<AgentMessage[]>(mockMessages);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);

  const handleSend = () => {
    if (!input.trim()) return;

    const newMessage: AgentMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date().toISOString(),
    };

    setMessages([...messages, newMessage]);
    setInput('');
    setIsStreaming(true);

    // Mock streaming response
    setTimeout(() => {
      const response: AgentMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'I\'d be happy to help build a landing page! 🔧',
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, response]);
      setIsStreaming(false);
    }, 1000);
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