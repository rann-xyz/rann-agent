"""
RANN Agent Web API - Backend proxy for AI chat

Handles API calls from the web interface to LLM providers,
avoiding CORS issues and keeping API keys secure.
"""

import os
import json
import asyncio
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Storage path for API keys
KEYS_DIR = Path.home() / ".rann_agent"
KEYS_DIR.mkdir(parents=True, exist_ok=True)
KEYS_FILE = KEYS_DIR / "keys.json"
CONFIG_FILE = KEYS_DIR / "config.json"


def load_keys():
    """Load API keys from storage"""
    if KEYS_FILE.exists():
        try:
            with open(KEYS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}


def save_keys(keys):
    """Save API keys to storage"""
    with open(KEYS_FILE, 'w') as f:
        json.dump(keys, f, indent=2)


def load_config():
    """Load config"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}


def save_config(config):
    """Save config"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


# Provider configurations
PROVIDERS = {
    "xkiro": {
        "name": "xkiro",
        "base_url": "https://api.xkiro.com",
        "default_model": "minimax/minimax-m2.7-highspeed:free",
        "api_type": "openai",  # OpenAI-compatible
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


@app.route('/api/status', methods=['GET'])
def status():
    """Check API status"""
    keys = load_keys()
    configured = list(keys.keys())
    
    return jsonify({
        "status": "online",
        "version": "1.0.0",
        "configured_providers": configured,
        "providers": {name: {"has_key": name in keys, "free": prov["free"]} 
                      for name, prov in PROVIDERS.items()}
    })


@app.route('/api/providers', methods=['GET'])
def list_providers():
    """List all available providers"""
    keys = load_keys()
    
    result = []
    for name, prov in PROVIDERS.items():
        result.append({
            "id": name,
            "name": prov["name"],
            "base_url": prov["base_url"],
            "default_model": prov["default_model"],
            "free": prov["free"],
            "api_type": prov["api_type"],
            "has_key": name in keys
        })
    
    return jsonify(result)


@app.route('/api/key/<provider>', methods=['GET'])
def get_key_status(provider):
    """Check if provider has API key"""
    keys = load_keys()
    has_key = provider in keys
    config = load_config()
    
    return jsonify({
        "provider": provider,
        "has_key": has_key,
        "model": config.get(f"{provider}_model", PROVIDERS.get(provider, {}).get("default_model", "")),
        "base_url": config.get(f"{provider}_url", PROVIDERS.get(provider, {}).get("base_url", ""))
    })


@app.route('/api/key/<provider>', methods=['POST'])
def set_key(provider):
    """Set API key for provider"""
    data = request.get_json()
    api_key = data.get('api_key', '').strip()
    model = data.get('model', '')
    base_url = data.get('base_url', '')
    
    if not api_key:
        return jsonify({"error": "API key is required"}), 400
    
    if provider not in PROVIDERS:
        return jsonify({"error": f"Unknown provider: {provider}"}), 400
    
    # Save key
    keys = load_keys()
    keys[provider] = api_key
    save_keys(keys)
    
    # Save config
    config = load_config()
    if model:
        config[f"{provider}_model"] = model
    if base_url:
        config[f"{provider}_url"] = base_url
    save_config(config)
    
    return jsonify({"success": True, "provider": provider})


@app.route('/api/key/<provider>', methods=['DELETE'])
def delete_key(provider):
    """Delete API key for provider"""
    keys = load_keys()
    if provider in keys:
        del keys[provider]
        save_keys(keys)
    
    return jsonify({"success": True, "provider": provider})


@app.route('/api/chat', methods=['POST'])
def chat():
    """Send chat message to LLM"""
    data = request.get_json()
    provider = data.get('provider', 'xkiro')
    message = data.get('message', '')
    history = data.get('history', [])
    model = data.get('model', '')
    
    if not message:
        return jsonify({"error": "Message is required"}), 400
    
    # Get API key
    keys = load_keys()
    if provider not in keys:
        return jsonify({"error": f"No API key configured for {provider}. Please add your API key first."}), 400
    
    api_key = keys[provider]
    config = load_config()
    
    # Get provider config
    if provider not in PROVIDERS:
        return jsonify({"error": f"Unknown provider: {provider}"}), 400
    
    prov = PROVIDERS[provider]
    base_url = config.get(f"{provider}_url", prov["base_url"])
    model = model or config.get(f"{provider}_model", prov["default_model"])
    
    # Build request based on API type
    try:
        if prov["api_type"] == "anthropic":
            return chat_anthropic(api_key, base_url, model, message, history)
        else:
            return chat_openai(api_key, base_url, model, message, history)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def chat_openai(api_key, base_url, model, message, history):
    """Chat with OpenAI-compatible API"""
    import urllib.request
    import urllib.error
    
    url = f"{base_url}/chat/completions"
    
    messages = [
        {"role": "system", "content": "You are RANN Agent, an autonomous AI assistant. You help users with coding, file operations, research, and general tasks. Be concise and helpful. Format code with triple backticks."}
    ]
    
    # Add history
    for msg in history:
        messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", "")
        })
    
    # Add current message
    messages.append({"role": "user", "content": message})
    
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": 2000,
        "temperature": 0.7
    }).encode('utf-8')
    
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        },
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode('utf-8'))
            content = data["choices"][0]["message"]["content"]
            return jsonify({"content": content})
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        return jsonify({"error": f"API Error {e.code}: {error_body[:200]}"}), e.code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def chat_anthropic(api_key, base_url, model, message, history):
    """Chat with Anthropic API"""
    import urllib.request
    import urllib.error
    
    url = f"{base_url}/v1/messages"
    
    messages = []
    for msg in history:
        messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", "")
        })
    messages.append({"role": "user", "content": message})
    
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": 2000
    }).encode('utf-8')
    
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        },
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode('utf-8'))
            content = data["content"][0]["text"]
            return jsonify({"content": content})
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        return jsonify({"error": f"API Error {e.code}: {error_body[:200]}"}), e.code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/test/<provider>', methods=['POST'])
def test_provider(provider):
    """Test if provider API key works"""
    keys = load_keys()
    
    if provider not in keys:
        return jsonify({"success": False, "error": "No API key"})
    
    # Try a simple chat
    result = chat_openai(
        keys[provider],
        PROVIDERS[provider]["base_url"],
        PROVIDERS[provider]["default_model"],
        "Hi",
        []
    )
    
    data = result.get_json()
    if "error" in data:
        return jsonify({"success": False, "error": data["error"]})
    
    return jsonify({"success": True})


@app.route('/api/system/check', methods=['GET'])
def system_check():
    """Check system compatibility"""
    checks = []
    
    # Python version
    import sys
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    checks.append({
        "name": "Python",
        "status": "ok" if sys.version_info >= (3, 8) else "error",
        "message": f"Python {py_version}"
    })
    
    # Check required modules
    required = ["flask", "urllib", "json", "pathlib"]
    for mod in required:
        try:
            __import__(mod)
            checks.append({"name": mod, "status": "ok", "message": f"{mod} available"})
        except:
            checks.append({"name": mod, "status": "error", "message": f"{mod} not found"})
    
    # Check network
    try:
        import urllib.request
        with urllib.request.urlopen("https://httpbin.org/get", timeout=5) as response:
            response.read()
        checks.append({"name": "Network", "status": "ok", "message": "Internet connection OK"})
    except:
        checks.append({"name": "Network", "status": "warning", "message": "Limited internet connection"})
    
    # Check disk space
    import shutil
    total, used, free = shutil.disk_usage("/")
    free_gb = free // (2**30)
    checks.append({
        "name": "Disk Space", 
        "status": "ok" if free_gb > 1 else "warning",
        "message": f"{free_gb}GB free"
    })
    
    return jsonify({
        "checks": checks,
        "overall": "ok" if all(c["status"] in ["ok", "warning"] for c in checks) else "error"
    })


if __name__ == '__main__':
    print("""
╔══════════════════════════════════════════════╗
║     RANN Agent Web API                       ║
║     Backend for AI Chat                      ║
╠══════════════════════════════════════════════╣
║  Local:  http://127.0.0.1:5555               ║
║  Network: http://0.0.0.0:5555                ║
╚══════════════════════════════════════════════╝
    """)
    app.run(host='0.0.0.0', port=5555, debug=False)