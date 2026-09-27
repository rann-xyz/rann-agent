/**
 * Terminal Component - xterm.js integration for RANN Web IDE
 * 
 * Features:
 * - Real-time PTY output streaming
 * - Keyboard input handling
 * - Terminal resize
 * - Mobile keyboard support
 * - ANSI escape sequence preservation
 */

import React, { useEffect, useRef, useCallback } from 'react';
import { Terminal } from 'xterm';
import { FitAddon } from '@xterm/addon-fit';
import { useTerminal } from '../hooks/useTerminal';
import { TerminalClient } from '../services/terminalClient';

interface TerminalProps {
  sessionId: string;
  projectId: string;
  userId: string;
}

export function TerminalComponent({ sessionId, projectId, userId }: TerminalProps): JSX.Element {
  const termRef = useRef<HTMLDivElement>(null);
  const clientRef = useRef<TerminalClient | null>(null);
  const terminalRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);

  const { status, sendInput, handleResize, handleDisconnect } = useTerminal({
    sessionId,
    projectId,
    userId,
  });

  // Initialize terminal
  useEffect(() => {
    if (!termRef.current) return;

    const term = new Terminal({
      cursorBlink: true,
      convertEol: true,
      scrollback: 1000,
      fontFamily: 'monospace',
      fontSize: 14,
      theme: {
        background: '#1e1e1e',
        foreground: '#d4d4d4',
        cursor: '#aeafad',
      },
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);

    term.open(termRef.current);
    fitAddon.fit();

    terminalRef.current = term;
    fitAddonRef.current = fitAddon;

    // Initialize terminal client
    const client = new TerminalClient({
      sessionId,
      userId,
      onOutput: (data) => {
        term.write(data);
      },
      onStatus: (newStatus) => {
        // Status update handled by hook
      },
      onExit: (code) => {
        term.write(`\r\n\r\n*** Terminal exited with code ${code} ***`);
      },
      onError: (code, message) => {
        term.write(`\r\n\r\n*** Terminal error: ${message} ***`);
      },
    });

    clientRef.current = client;
    client.connect();

    return () => {
      client.disconnect();
      term.dispose();
    };
  }, [sessionId, userId]);

  // Handle terminal input
  const handleInput = useCallback((data: string) => {
    if (!clientRef.current) return;
    sendInput(data);
  }, [sendInput]);

  // Handle terminal resize
  useEffect(() => {
    const handleResize = () => {
      if (fitAddonRef.current && terminalRef.current) {
        fitAddonRef.current.fit();
        if (clientRef.current && terminalRef.current) {
          const { cols, rows } = terminalRef.current;
          handleResize(cols, rows);
        }
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [handleResize]);

  // Handle keyboard shortcuts for mobile
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!clientRef.current || !terminalRef.current) return;

      // Handle Ctrl+C
      if (e.ctrlKey && e.key === 'c') {
        e.preventDefault();
        clientRef.current.sendInput('\x03'); // Ctrl+C
      }
      // Handle Ctrl+D
      else if (e.ctrlKey && e.key === 'd') {
        e.preventDefault();
        clientRef.current.sendInput('\x04'); // Ctrl+D
      }
      // Handle Ctrl+L
      else if (e.ctrlKey && e.key === 'l') {
        e.preventDefault();
        clientRef.current.sendInput('\x0c'); // Ctrl+L
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <div className="h-full flex flex-col">
      {/* Status bar */}
      <div className="flex items-center justify-between p-2 bg-gray-800 text-gray-300 text-sm">
        <div className="flex items-center space-x-2">
          <span className={`w-2 h-2 rounded-full ${
            status === 'connected' ? 'bg-green-500' : 
            status === 'connecting' ? 'bg-yellow-500' : 
            status === 'error' ? 'bg-red-500' : 'bg-gray-500'
          }`} />
          <span className="font-mono text-xs">
            {status === 'connected' ? '● connected' : 
             status === 'connecting' ? '○ connecting' : 
             status === 'disconnected' ? '○ disconnected' : 
             status === 'error' ? '○ error' : '○ ' + status}
          </span>
        </div>
        <div className="text-xs text-gray-500">
          /workspace • non-root
        </div>
      </div>

      {/* Terminal */}
      <div 
        ref={termRef} 
        className="flex-1 terminal-container"
        style={{ minHeight: '100%' }}
      />

      {/* Mobile keyboard toolbar */}
      <MobileKeyboardToolbar onKey={(key) => clientRef.current?.sendInput(key)} />
    </div>
  );
}

/**
 * Mobile keyboard toolbar with terminal control keys
 */
function MobileKeyboardToolbar({ onKey }: { onKey: (key: string) => void }): JSX.Element {
  const specialKeys = [
    { label: 'ESC', value: '\x1b', primary: true },
    { label: 'TAB', value: '\t', primary: true },
    { label: '⎋', value: '\x1b', secondary: true },
    { label: '←', value: '\x1b[D' },
    { label: '↑', value: '\x1b[A' },
    { label: '↓', value: '\x1b[B' },
    { label: '→', value: '\x1b[C' },
    { label: 'HOME', value: '\x1bOH' },
    { label: 'END', value: '\x1bOF' },
    { label: 'PG↑', value: '\x1b[5~' },
    { label: 'PG↓', value: '\x1b[6~' },
    { label: 'DEL', value: '\x1b[3~' },
    { label: 'INS', value: '\x1b[2~' },
  ];

  const controlKeys = [
    { label: 'Ctrl', value: 'ctrl', ctrl: true },
    { label: 'C', value: '\x03', ctrl: true },
    { label: 'D', value: '\x04', ctrl: true },
    { label: 'L', value: '\x0c', ctrl: true },
    { label: 'Z', value: '\x1a', ctrl: true },
    { label: 'A', value: '\x01', ctrl: true },
    { label: 'E', value: '\x05', ctrl: true },
    { label: 'K', value: '\x0b', ctrl: true },
  ];

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-gray-900 border-t border-gray-700 p-2">
      {/* Special keys */}
      <div className="flex flex-wrap gap-1 mb-2">
        {specialKeys.map((key) => (
          <button
            key={key.value}
            onClick={() => onKey(key.value)}
            className={`px-2 py-1 text-xs font-mono rounded
              ${key.primary ? 'bg-blue-600 hover:bg-blue-500' : 'bg-gray-700 hover:bg-gray-600'}
              text-white transition-colors`}
          >
            {key.label}
          </button>
        ))}
      </div>

      {/* Control keys */}
      <div className="flex flex-wrap gap-1">
        {controlKeys.map((key) => (
          <button
            key={key.value}
            onClick={() => onKey(key.value)}
            className={`px-2 py-1 text-xs font-mono rounded
              bg-purple-600 hover:bg-purple-500 text-white transition-colors`}
          >
            {key.ctrl ? `Ctrl+${key.label}` : key.label}
          </button>
        ))}
      </div>
    </div>
  );
}