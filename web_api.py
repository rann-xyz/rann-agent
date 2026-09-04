#!/usr/bin/env python3
"""
RANN Agent Web API - Simple HTTP server for AI chat

Uses Python's built-in http.server - no Flask needed.
Stores API keys securely in ~/.rann_agent/keys.json
"""

import os
import json
import base64
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Storage
KEYS_DIR = Path.home() / ".rann_agent"
KEYS_DIR.mkdir(parents=True, exist_ok=True)
KEYS_FILE = KEYS_DIR / "keys.json"
CONFIG_FILE = KEYS_DIR / "config.json"

# Providers config
PROVIDERS = {
    "xkiro": {
        "name": "xkiro",
        "base_url": "https://api.xkiro.com/v1",
        "default_model": "minimax/minimax-m2.7-highspeed:free",
        "api_type": "openai",
        "free": True
    },
    "groq": {
        "name": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.1-70b-versatile",
        "api_type": "openai",
        "free": True
    },
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "api_type": "openai",
        "free": True
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
        "api_type": "openai",
        "free": False
    },
    "anthropic": {
        "name": "Anthropic",
        "base_url": "https://api.anthropic.com",
        "default_model": "claude-sonnet-4-20250514",
        "api_type": "anthropic",
        "free": False
    },
    "ollama": {
        "name": "Ollama",
        "base_url": "http://localhost:11434/v1",
        "default_model": "llama3.2",
        "api_type": "openai",
        "free": True
    }
}


def load_keys():
    if KEYS_FILE.exists():
        try:
            with open(KEYS_FILE) as f:
                return json.load(f)
        except:
            pass
    return {}


def save_keys(keys):
    with open(KEYS_FILE, 'w') as f:
        json.dump(keys, f, indent=2)


def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except:
            pass
    return {}


def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


class APIHandler(BaseHTTPRequestHandler):
    # Disable logging
    def log_message(self, format, *args):
        pass

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/api/status':
            keys = load_keys()
            self.send_json({
                'status': 'online',
                'version': '1.0.0',
                'configured_providers': list(keys.keys()),
                'providers': {name: {'has_key': name in keys, 'free': prov['free']} 
                             for name, prov in PROVIDERS.items()}
            })

        elif path == '/api/providers':
            keys = load_keys()
            result = []
            for name, prov in PROVIDERS.items():
                result.append({
                    'id': name,
                    'name': prov['name'],
                    'base_url': prov['base_url'],
                    'default_model': prov['default_model'],
                    'free': prov['free'],
                    'api_type': prov['api_type'],
                    'has_key': name in keys
                })
            self.send_json(result)

        elif path.startswith('/api/key/'):
            provider = path.split('/')[3]
            keys = load_keys()
            config = load_config()
            has_key = provider in keys
            self.send_json({
                'provider': provider,
                'has_key': has_key,
                'model': config.get(f'{provider}_model', PROVIDERS.get(provider, {}).get('default_model', '')),
                'base_url': config.get(f'{provider}_url', PROVIDERS.get(provider, {}).get('base_url', ''))
            })

        elif path == '/api/system/check':
            import sys
            import shutil
            checks = [
                {'name': 'Python', 'status': 'ok' if sys.version_info >= (3, 8) else 'error',
                 'message': f'Python {sys.version_info.major}.{sys.version_info.minor}'},
                {'name': 'urllib', 'status': 'ok', 'message': 'Available'},
                {'name': 'Memory', 'status': 'ok', 'message': 'Ready'},
            ]
            total, used, free = shutil.disk_usage('/')
            free_gb = free // (2**30)
            checks.append({'name': 'Disk Space', 'status': 'ok' if free_gb > 1 else 'warning',
                          'message': f'{free_gb}GB free'})
            self.send_json({'checks': checks, 'overall': 'ok'})

        else:
            self.send_json({'error': 'Not found'}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # Read body
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else '{}'

        try:
            data = json.loads(body) if body else {}
        except:
            data = {}

        if path == '/api/chat':
            self.handle_chat(data)
        elif path.startswith('/api/key/'):
            provider = path.split('/')[3]
            self.handle_set_key(provider, data)
        elif path.startswith('/api/test/'):
            provider = path.split('/')[3]
            self.handle_test(provider)
        else:
            self.send_json({'error': 'Not found'}, 404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith('/api/key/'):
            provider = path.split('/')[3]
            keys = load_keys()
            if provider in keys:
                del keys[provider]
                save_keys(keys)
            self.send_json({'success': True, 'provider': provider})
        else:
            self.send_json({'error': 'Not found'}, 404)

    def handle_chat(self, data):
        provider = data.get('provider', 'groq')
        message = data.get('message', '')
        history = data.get('history', [])

        if not message:
            self.send_json({'error': 'Message is required'}, 400)
            return

        keys = load_keys()
        if provider not in keys:
            self.send_json({'error': f'No API key for {provider}. Add key in Settings.'}, 400)
            return

        api_key = keys[provider]
        config = load_config()

        if provider not in PROVIDERS:
            self.send_json({'error': f'Unknown provider: {provider}'}, 400)
            return

        prov = PROVIDERS[provider]
        base_url = config.get(f'{provider}_url', prov['base_url'])
        model = data.get('model') or config.get(f'{provider}_model', prov['default_model'])

        try:
            if prov['api_type'] == 'anthropic':
                self.chat_anthropic(api_key, base_url, model, message, history)
            else:
                self.chat_openai(api_key, base_url, model, message, history)
        except Exception as e:
            self.send_json({'error': str(e)}, 500)

    def chat_openai(self, api_key, base_url, model, message, history):
        import urllib.request
        import urllib.error

        url = f'{base_url}/chat/completions'

        messages = [
            {'role': 'system', 'content': 'You are RANN Agent. Be concise and helpful. Format code with triple backticks.'}
        ]
        for msg in history:
            messages.append({'role': msg.get('role', 'user'), 'content': msg.get('content', '')})
        messages.append({'role': 'user', 'content': message})

        payload = json.dumps({
            'model': model,
            'messages': messages,
            'max_tokens': 2000,
            'temperature': 0.7
        }).encode('utf-8')

        req = urllib.request.Request(url, data=payload, headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json'
        }, method='POST')

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode())
                content = result['choices'][0]['message']['content']
                self.send_json({'content': content})
        except urllib.error.HTTPError as e:
            err = e.read().decode()[:200]
            self.send_json({'error': f'API Error {e.code}: {err}'}, e.code)
        except Exception as e:
            self.send_json({'error': str(e)}, 500)

    def chat_anthropic(self, api_key, base_url, model, message, history):
        import urllib.request
        import urllib.error

        url = f'{base_url}/v1/messages'

        messages = []
        for msg in history:
            messages.append({'role': msg.get('role', 'user'), 'content': msg.get('content', '')})
        messages.append({'role': 'user', 'content': message})

        payload = json.dumps({
            'model': model,
            'messages': messages,
            'max_tokens': 2000
        }).encode('utf-8')

        req = urllib.request.Request(url, data=payload, headers={
            'Content-Type': 'application/json',
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json'
        }, method='POST')

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode())
                content = result['content'][0]['text']
                self.send_json({'content': content})
        except urllib.error.HTTPError as e:
            err = e.read().decode()[:200]
            self.send_json({'error': f'API Error {e.code}: {err}'}, e.code)
        except Exception as e:
            self.send_json({'error': str(e)}, 500)

    def handle_set_key(self, provider, data):
        api_key = data.get('api_key', '').strip()
        model = data.get('model', '')
        base_url = data.get('base_url', '')

        if not api_key:
            self.send_json({'error': 'API key is required'}, 400)
            return

        if provider not in PROVIDERS:
            self.send_json({'error': f'Unknown provider: {provider}'}, 400)
            return

        keys = load_keys()
        keys[provider] = api_key
        save_keys(keys)

        config = load_config()
        if model:
            config[f'{provider}_model'] = model
        if base_url:
            config[f'{provider}_url'] = base_url
        save_config(config)

        self.send_json({'success': True, 'provider': provider})

    def handle_test(self, provider):
        keys = load_keys()
        if provider not in keys:
            self.send_json({'success': False, 'error': 'No API key'})

        prov = PROVIDERS.get(provider, {})
        try:
            self.chat_openai(keys[provider], prov['base_url'], prov['default_model'], 'Hi', [])
            self.send_json({'success': True})
        except Exception as e:
            self.send_json({'success': False, 'error': str(e)})


def run(port=5555):
    server = HTTPServer(('0.0.0.0', port), APIHandler)
    print(f'''
╔══════════════════════════════════════════════╗
║     RANN Agent Web API                       ║
║     Backend for AI Chat                      ║
╠══════════════════════════════════════════════╣
║  Local:   http://127.0.0.1:{port}              ║
║  Network: http://0.0.0.0:{port}                ║
╚══════════════════════════════════════════════╝
    ''')
    server.serve_forever()


if __name__ == '__main__':
    run()