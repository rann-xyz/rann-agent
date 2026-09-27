/**
 * TerminalClient - WebSocket terminal client for RANN Web IDE
 * 
 * Handles communication between xterm.js and the backend PTY terminal.
 * 
 * PROTOCOL:
 * Client -> Server:
 *   { "type": "input", "data": "..." }
 *   { "type": "resize", "cols": 120, "rows": 40 }
 *   { "type": "ping" }
 * 
 * Server -> Client:
 *   { "type": "output", "data": "..." }
 *   { "type": "status", "status": "connected" }
 *   { "type": "exit", "code": 0 }
 *   { "type": "error", "code": "...", "message": "..." }
 */

import { EventCallback } from 'xterm';

export interface TerminalClientOptions {
  apiUrl?: string;
  sessionId: string;
  userId: string;
  onOutput?: (data: string) => void;
  onStatus?: (status: TerminalStatus) => void;
  onExit?: (code: number) => void;
  onError?: (code: string, message: string) => void;
  onPing?: () => void;
  onPong?: () => void;
}

export type TerminalStatus = 'connecting' | 'connected' | 'disconnected' | 'reconnecting' | 'closed' | 'error';
export type TerminalError = 'TERMINAL_ALREADY_ATTACHED' | 'SANDBOX_UNAVAILABLE' | 'CONNECTION_FAILED' | 'TIMEOUT';

export class TerminalClient {
  private options: TerminalClientOptions;
  private ws: WebSocket | null = null;
  private _status: TerminalStatus = 'disconnected';
  private heartbeatInterval: ReturnType<typeof setInterval> | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;

  constructor(options: TerminalClientOptions) {
    this.options = {
      apiUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
      ...options,
    };
  }

  /** Get current terminal status */
  get status(): TerminalStatus {
    return this._status;
  }

  /** Check if connected */
  get isConnected(): boolean {
    return this._status === 'connected';
  }

  /**
   * Connect to the terminal session
   */
  async connect(): Promise<void> {
    if (this.isConnected) return;

    this._status = 'connecting';
    this.options.onStatus?.(this._status);

    try {
      const wsUrl = this.getWebSocketUrl();
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this._status = 'connected';
        this.reconnectAttempts = 0;
        this.options.onStatus?.(this._status);
        this.startHeartbeat();
      };

      this.ws.onmessage = (event) => {
        this.handleMessage(JSON.parse(event.data));
      };

      this.ws.onclose = (event) => {
        this.handleClose(event);
      };

      this.ws.onerror = (error) => {
        this.handleError(error);
      };
    } catch (error) {
      this._status = 'error';
      this.options.onError?.('CONNECTION_FAILED', error instanceof Error ? error.message : 'Unknown error');
    }
  }

  /** Disconnect from terminal */
  async disconnect(): Promise<void> {
    this.stopHeartbeat();
    
    if (this.ws) {
      try {
        this.ws.close();
      } catch {}
      this.ws = null;
    }

    this._status = 'disconnected';
    this.options.onStatus?.(this._status);
  }

  /** Reconnect to terminal */
  async reconnect(): Promise<void> {
    this._status = 'reconnecting';
    this.options.onStatus?.(this._status);
    await this.connect();
  }

  /** Send input to terminal */
  sendInput(data: string): void {
    if (!this.isConnected || !this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }

    const message = {
      type: 'input',
      data,
    };

    this.ws.send(JSON.stringify(message));
  }

  /** Resize the terminal */
  resize(cols: number, rows: number): void {
    if (!this.isConnected || !this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }

    const message = {
      type: 'resize',
      cols,
      rows,
    };

    this.ws.send(JSON.stringify(message));
  }

  /** Send ping to check connection health */
  ping(): void {
    if (!this.isConnected || !this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }

    this.ws.send(JSON.stringify({ type: 'ping' }));
  }

  /** Handle incoming WebSocket message */
  private handleMessage(message: any): void {
    if (!message.type) return;

    switch (message.type) {
      case 'output':
        this.options.onOutput?.(message.data || '');
        break;
      case 'status':
        this._status = message.status;
        this.options.onStatus?.(this._status);
        break;
      case 'exit':
        this._status = 'closed';
        this.options.onStatus?.(this._status);
        this.options.onExit?.(message.code || 0);
        break;
      case 'error':
        this._status = 'error';
        this.options.onStatus?.(this._status);
        this.options.onError?.(message.code || 'UNKNOWN', message.message || 'Unknown error');
        break;
      case 'pong':
        this.options.onPong?.();
        break;
    }

    // Update last activity
    this.reconnectAttempts = 0;
  }

  /** Handle WebSocket close */
  private handleClose(event: CloseEvent): void {
    this.stopHeartbeat();

    if (this._status === 'connecting') {
      // Failed to connect
      this._status = 'error';
      this.options.onStatus?.(this._status);
      this.options.onError?.('CONNECTION_FAILED', 'Failed to connect to terminal');
      return;
    }

    if (this._status === 'connected') {
      // Unexpected disconnect
      this._status = 'disconnected';
      this.options.onStatus?.(this._status);

      // Auto-reconnect
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        setTimeout(() => {
          this.reconnectAttempts++;
          this.reconnect();
        }, this.reconnectDelay * this.reconnectAttempts);
      }
    }
  }

  /** Handle WebSocket error */
  private handleError(error: Event): void {
    this._status = 'error';
    this.options.onStatus?.(this._status);
    this.options.onError?.('CONNECTION_FAILED', error instanceof ErrorEvent ? error.message : 'WebSocket error');
  }

  /** Start heartbeat interval */
  private startHeartbeat(): void {
    this.heartbeatInterval = setInterval(() => {
      this.ping();
    }, 30000); // Ping every 30 seconds
  }

  /** Stop heartbeat interval */
  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  /** Get WebSocket URL */
  private getWebSocketUrl(): string {
    const apiUrl = this.options.apiUrl;
    const wsProtocol = apiUrl.startsWith('https') ? 'wss' : 'ws';
    const host = apiUrl.replace(/^https?:\/\//, '');
    return `${wsProtocol}://${host}/ws/projects/${this.options.sessionId}/terminal`;
  }
}