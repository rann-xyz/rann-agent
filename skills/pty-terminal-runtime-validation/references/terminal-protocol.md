# WebSocket Terminal Protocol

Protocol specification for RANN PTY terminal communication.

## Overview

The terminal protocol enables real-time bidirectional communication between browser-based terminal (xterm.js) and the server-side PTY shell inside Docker container.

## Message Structure

All messages are JSON objects with a `type` field.

```json
{
  "type": "<message_type>",
  "data": <payload>,
  "code": "<error_code>"  // optional, for errors
}
```

## Client → Server Messages

### input

Send raw terminal input to PTY stdin.

```json
{
  "type": "input",
  "data": "ls -la\r\n"
}
```

**Note**: `\r\n` (CRLF) is the traditional terminal newline format.

### resize

Change terminal dimensions.

```json
{
  "type": "resize",
  "cols": 120,
  "rows": 40
}
```

Server calls Docker API: `exec_resize(exec_id, rows, cols)`

### ping

Health check heartbeat.

```json
{
  "type": "ping"
}
```

## Server → Client Messages

### output

Streaming PTY output (stdout/stderr multiplexed).

```json
{
  "type": "output",
  "data": "total 16\ndrwxr-xr-x 2 user user 4096 ...\n"
}
```

**Properties**:
- Sent immediately when data arrives from PTY
- ANSI escape sequences preserved
- May contain partial lines
- Multiple output messages may arrive in sequence

### status

Current terminal status.

```json
{
  "type": "status",
  "status": "connected",
  "cols": 120,
  "rows": 32
}
```

**Status values**:
- `connecting`: Initial connection
- `connected`: WebSocket attached, PTY ready
- `running`: Active command execution
- `idle`: Waiting for input
- `disconnecting`: WebSocket closing
- `closed`: Session ended
- `error`: Session in error state

### exit

Terminal session ended.

```json
{
  "type": "exit",
  "code": 0
}
```

**Exit codes**:
- `0`: Normal shell exit
- `1-126`: Command error (inside shell)
- `130`: Interrupted by SIGINT (Ctrl+C)
- `137`: Killed by SIGKILL (timeout)
- `-1`: Terminal error

### error

Error occurred.

```json
{
  "type": "error",
  "code": "SANDBOX_UNAVAILABLE",
  "message": "Docker daemon not available"
}
```

**Common error codes**:
- `AUTHENTICATION_REQUIRED`: Invalid or expired session
- `PROJECT_NOT_FOUND`: Project does not exist
- `ACCESS_DENIED`: Not project owner
- `SANDBOX_NOT_RUNNING`: Container not started
- `SANDBOX_NOT_FOUND`: Container does not exist
- `DOCKER_ERROR`: Docker API failure
- `PTY_START_FAILED`: Could not start shell
- `PROCESSING_ERROR`: Internal error

### pong

Response to ping.

```json
{
  "type": "pong"
}
```

## Raw Terminal Encoding

### UTF-8 Handling

All data is UTF-8 encoded with error replacement:

```python
# Server output
data.decode('utf-8', errors='replace')

# Client input
data.encode('utf-8', errors='replace')
```

### Special Terminal Bytes

Characters that may appear in input:
- `\r` (13) - Carriage return (Enter)
- `\n` (10) - Line feed
- `\x03` (3) - Ctrl+C (SIGINT)
- `\x04` (4) - Ctrl+D (EOF)
- `\x1b` (27) - ESC - Start of ANSI sequence
- `\x7f` (127) - DEL - Backspace/Delete

### ANSI Escape Sequences

Sequences are passed through unchanged:

| Sequence | Effect |
|----------|--------|
| `\033[31m` | Red foreground |
| `\033[0m` | Reset |
| `\033[2J` | Clear screen |
| `\033[H` | Move cursor to home |
| `\033[?25l` | Hide cursor |
| `\033[?25h` | Show cursor |

## xterm.js Integration

### Connection

```javascript
const ws = new WebSocket('ws://api.rann.xyz/ws/projects/' + projectId + '/terminal');
```

### Output Handler

```javascript
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'output') {
    term.write(msg.data);
  } else if (msg.type === 'exit') {
    term.writeln(`\r\nSession ended with code ${msg.code}`);
    term.dispose();
  } else if (msg.type === 'error') {
    term.writeln(`\r\nError: ${msg.message}`);
  }
};
```

### Input Handler

```javascript
term.onData((data) => {
  ws.send(JSON.stringify({
    type: 'input',
    data: data
  }));
});
```

### Resize Handler

```javascript
window.addEventListener('resize', () => {
  const { cols, rows } = term.cols, term.rows;
  ws.send(JSON.stringify({
    type: 'resize',
    cols: cols,
    rows: rows
  }));
});
```

## Protocol Flow

```
Client                Server                  Docker PTY
   |                     |                        |
   |--- connect -------->|                        |
   |                     |                        |
   |<-- output ---------->                        |
   |                     |                        |
   |--- input ---------->---- write() ----------->|
   |                     |<--- read() ------------|
   |<-- output ---------|                        |
   |                     |                        |
   |--- resize --------->---- exec_resize ------>|
   |                     |                        |
   |<-- exit ------------|---- EOF detected -----|
   |                     |                        |
   |--- close ----------->---- kill exec ------|
   |                     |                        |
```

## Error Recovery

### Connection Lost

```javascript
ws.onclose = () => {
  if (!term._closed) {
    term.writeln('\r\nConnection lost. Reconnecting...');
    // Implement reconnect logic
  }
};
```

### Message Overflow

Messages exceeding `TERMINAL_MAX_MESSAGE_BYTES` are truncated to prevent memory exhaustion.

## Security Considerations

1. **Never trust client input**: All input is forwarded to PTY without parsing
2. **Session ownership**: Every operation validates project ownership
3. **Resource limits**: Output truncated at MAX_MESSAGE_BYTES
4. **Session limits**: Max concurrent sessions enforced
5. **No Docker escape**: Input never reaches host shell