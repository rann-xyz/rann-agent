"""
API Key Management for RANN Agent

Secure API key storage and provider configuration.
"""

import os
import json
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass
from cryptography.fernet import Fernet
import base64
import hashlib


@dataclass
class APIKeyConfig:
    """Configuration for an API provider"""
    name: str
    key: str  # Will be masked in display
    base_url: str
    model: str
    enabled: bool = True


class APIKeyManager:
    """
    Manages API keys securely with encryption.
    Keys are stored encrypted in ~/.rann_agent/keys.enc
    """
    
    def __init__(self, base_path: str = None):
        self.base_path = Path(base_path) if base_path else Path.home() / ".rann_agent"
        self.keys_file = self.base_path / "keys.enc"
        self.config_file = self.base_path / "provider_config.json"
        self._ensure_dir()
        self._cipher = self._get_cipher()
    
    def _ensure_dir(self):
        """Ensure directory exists"""
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def _get_cipher(self) -> Fernet:
        """Get or create encryption cipher"""
        key_file = self.base_path / ".key"
        
        if not key_file.exists():
            # Generate new key
            key = Fernet.generate_key()
            key_file.write_bytes(key)
            key_file.chmod(0o600)  # Readable only by owner
        else:
            key = key_file.read_bytes()
        
        return Fernet(key)
    
    def save_key(self, provider: str, api_key: str, base_url: str = None, model: str = None) -> bool:
        """Save an API key (encrypted)"""
        try:
            keys = self._load_keys()
            
            # Encrypt the API key
            encrypted_key = self._cipher.encrypt(api_key.encode()).decode()
            
            keys[provider] = {
                "encrypted_key": encrypted_key,
                "base_url": base_url or "",
                "model": model or "",
                "added_at": str(Path(__file__).stat().st_mtime if os.path.exists(__file__) else "unknown")
            }
            
            self._save_keys(keys)
            return True
        except Exception as e:
            print(f"Error saving key: {e}")
            return False
    
    def get_key(self, provider: str) -> Optional[str]:
        """Get decrypted API key"""
        keys = self._load_keys()
        
        if provider not in keys:
            return None
        
        try:
            encrypted_key = keys[provider]["encrypted_key"]
            return self._cipher.decrypt(encrypted_key.encode()).decode()
        except Exception:
            return None
    
    def remove_key(self, provider: str) -> bool:
        """Remove an API key"""
        keys = self._load_keys()
        
        if provider in keys:
            del keys[provider]
            self._save_keys(keys)
            return True
        return False
    
    def list_providers(self) -> List[str]:
        """List all saved providers"""
        keys = self._load_keys()
        return list(keys.keys())
    
    def has_key(self, provider: str) -> bool:
        """Check if provider has a key"""
        return provider in self._load_keys()
    
    def _load_keys(self) -> Dict:
        """Load encrypted keys"""
        if not self.keys_file.exists():
            return {}
        
        try:
            with open(self.keys_file, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def _save_keys(self, keys: Dict):
        """Save encrypted keys"""
        with open(self.keys_file, 'w') as f:
            json.dump(keys, f, indent=2)
        self.keys_file.chmod(0o600)
    
    @staticmethod
    def mask_key(key: str) -> str:
        """Mask API key for display"""
        if not key or len(key) < 8:
            return "***"
        
        if len(key) <= 12:
            return key[:4] + "***" + key[-4:]
        
        return key[:6] + "***" + key[-4:]


class ProviderManager:
    """
    Manages LLM provider configurations.
    """
    
    # Supported providers with their configs
    PROVIDERS = {
        "xkiro": {
            "name": "xkiro",
            "base_url": "https://api.xkiro.com",
            "default_model": "minimax/minimax-m2.7-highspeed:free",
            "free": True,
            "description": "Free tier available"
        },
        "anthropic": {
            "name": "Anthropic",
            "base_url": "https://api.anthropic.com",
            "default_model": "claude-sonnet-4-20250514",
            "free": False,
            "description": "Claude models"
        },
        "openai": {
            "name": "OpenAI",
            "base_url": "https://api.openai.com/v1",
            "default_model": "gpt-4o",
            "free": False,
            "description": "GPT-4 models"
        },
        "groq": {
            "name": "Groq",
            "base_url": "https://api.groq.com/openai/v1",
            "default_model": "llama-3.1-70b-versatile",
            "free": True,
            "description": "Fast free tier"
        },
        "ollama": {
            "name": "Ollama",
            "base_url": "http://localhost:11434/v1",
            "default_model": "llama3.2",
            "free": True,
            "description": "Local models"
        },
        "deepseek": {
            "name": "DeepSeek",
            "base_url": "https://api.deepseek.com/v1",
            "default_model": "deepseek-chat",
            "free": True,
            "description": "DeepSeek V3"
        }
    }
    
    def __init__(self):
        self.key_manager = APIKeyManager()
    
    def get_provider_config(self, provider: str) -> Optional[APIKeyConfig]:
        """Get full config for a provider"""
        if provider not in self.PROVIDERS:
            return None
        
        prov = self.PROVIDERS[provider]
        api_key = self.key_manager.get_key(provider)
        
        if not api_key:
            return None
        
        return APIKeyConfig(
            name=provider,
            key=api_key,
            base_url=prov["base_url"],
            model=prov["default_model"],
            enabled=True
        )
    
    def list_available(self) -> List[Dict]:
        """List all providers with availability status"""
        result = []
        
        for name, prov in self.PROVIDERS.items():
            has_key = self.key_manager.has_key(name)
            result.append({
                "name": name,
                "display_name": prov["name"],
                "base_url": prov["base_url"],
                "default_model": prov["default_model"],
                "free": prov["free"],
                "description": prov["description"],
                "has_key": has_key,
                "key_masked": self.key_manager.mask_key(self.key_manager.get_key(name)) if has_key else None
            })
        
        return result
    
    def test_provider(self, provider: str) -> Dict:
        """Test if provider API key works"""
        config = self.get_provider_config(provider)
        
        if not config:
            return {"success": False, "error": "No API key configured"}
        
        try:
            import aiohttp
            import asyncio
            
            async def test():
                async with aiohttp.ClientSession() as session:
                    headers = {
                        "Authorization": f"Bearer {config.key}",
                        "Content-Type": "application/json"
                    }
                    
                    # Different providers have different test endpoints
                    if provider == "anthropic":
                        data = {"model": config.model, "max_tokens": 10, "messages": [{"role": "user", "content": "hi"}]}
                        url = f"{config.base_url}/v1/messages"
                        headers["x-api-key"] = config.key
                        headers.pop("Authorization")
                    else:
                        data = {"model": config.model, "max_tokens": 10, "messages": [{"role": "user", "content": "hi"}]}
                        url = f"{config.base_url}/chat/completions"
                    
                    async with session.post(url, json=data, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status == 200:
                            return {"success": True}
                        else:
                            text = await resp.text()
                            return {"success": False, "error": f"Status {resp.status}: {text[:100]}"}
            
            return asyncio.run(test())
        except Exception as e:
            return {"success": False, "error": str(e)}


# CLI commands for API key management
def register_api_commands(cli):
    """Register API key management commands."""
    
    @cli.group("api-key")
    def api_key_group():
        """Manage API keys for LLM providers."""
        pass
    
    @api_key_group.command("add")
    @click.argument("provider")
    @click.argument("api_key")
    @click.option("--base-url", default=None, help="Custom base URL")
    @click.option("--model", default=None, help="Default model")
    def add_key(provider: str, api_key: str, base_url: str, model: str):
        """Add an API key for a provider."""
        manager = APIKeyManager()
        
        # Get default base_url and model from provider if not provided
        if provider in ProviderManager.PROVIDERS:
            prov = ProviderManager.PROVIDERS[provider]
            base_url = base_url or prov["base_url"]
            model = model or prov["default_model"]
        
        if manager.save_key(provider, api_key, base_url, model):
            masked = manager.mask_key(api_key)
            click.echo(f"✅ Added API key for {provider}: {masked}")
        else:
            click.echo(f"❌ Failed to save API key for {provider}")
    
    @api_key_group.command("remove")
    @click.argument("provider")
    def remove_key(provider: str):
        """Remove an API key."""
        manager = APIKeyManager()
        
        if manager.remove_key(provider):
            click.echo(f"✅ Removed API key for {provider}")
        else:
            click.echo(f"❌ No API key found for {provider}")
    
    @api_key_group.command("list")
    def list_keys():
        """List all API keys (masked)."""
        pm = ProviderManager()
        providers = pm.list_available()
        
        click.echo("\n🔑 API Key Status\n")
        
        for p in providers:
            status = "✅" if p["has_key"] else "❌"
            key_info = f" ({p['key_masked']})" if p["has_key"] else " (not configured)"
            free_tag = " [FREE]" if p["free"] else ""
            
            click.echo(f"  {status} {p['display_name']}{free_tag}{key_info}")
            click.echo(f"     Model: {p['default_model']}")
            click.echo(f"     {p['description']}")
            click.echo()
    
    @api_key_group.command("test")
    @click.argument("provider")
    def test_key(provider: str):
        """Test if an API key works."""
        pm = ProviderManager()
        result = pm.test_provider(provider)
        
        if result["success"]:
            click.echo(f"✅ {provider} API key works!")
        else:
            click.echo(f"❌ {provider} API key test failed: {result.get('error', 'Unknown error')}")
    
    @api_key_group.command("setup")
    @click.argument("provider")
    def setup_provider(provider: str):
        """Interactive setup for a provider."""
        pm = ProviderManager()
        
        if provider not in ProviderManager.PROVIDERS:
            click.echo(f"Unknown provider: {provider}")
            click.echo(f"Available: {', '.join(pm.PROVIDERS.keys())}")
            return
        
        prov = ProviderManager.PROVIDERS[provider]
        click.echo(f"\n📝 Setup {prov['name']}")
        click.echo(f"   Default model: {prov['default_model']}")
        click.echo(f"   Base URL: {prov['base_url']}")
        click.echo()
        
        api_key = click.prompt("Enter your API key", type=str, hide_input=True)
        
        manager = APIKeyManager()
        if manager.save_key(provider, api_key, prov["base_url"], prov["default_model"]):
            click.echo(f"✅ API key saved for {provider}")
            
            # Test it
            click.echo("Testing connection...")
            result = pm.test_provider(provider)
            if result["success"]:
                click.echo("✅ Connection test passed!")
            else:
                click.echo(f"⚠️ Connection test failed: {result.get('error', 'Unknown')}")
        else:
            click.echo(f"❌ Failed to save API key")


# Need click for CLI
import click