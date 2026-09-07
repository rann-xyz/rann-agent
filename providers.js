// Provider configurations — matches web_api.py PROVIDERS
const PROVIDERS = {
  groq: {
    name: "Groq",
    base_url: "https://api.groq.com/openai/v1",
    default_model: "llama-3.1-70b-versatile",
    api_type: "openai",
    free: true,
    models: ["llama-3.1-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma-7b-it"]
  },
  deepseek: {
    name: "DeepSeek",
    base_url: "https://api.deepseek.com/v1",
    default_model: "deepseek-chat",
    api_type: "openai",
    free: true,
    models: ["deepseek-chat", "deepseek-coder"]
  },
  openai: {
    name: "OpenAI",
    base_url: "https://api.openai.com/v1",
    default_model: "gpt-4o",
    api_type: "openai",
    free: false,
    models: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]
  },
  anthropic: {
    name: "Anthropic",
    base_url: "https://api.anthropic.com/v1",
    default_model: "claude-sonnet-4-20250514",
    api_type: "anthropic",
    free: false,
    models: ["claude-sonnet-4-20250514", "claude-opus-4-20250514", "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"]
  },
  gemini: {
    name: "Google Gemini",
    base_url: "https://generativelanguage.googleapis.com/v1beta",
    default_model: "gemini-1.5-flash",
    api_type: "gemini",
    free: true,
    models: ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-1.0-pro"]
  },
  ollama: {
    name: "Ollama",
    base_url: "http://localhost:11434/v1",
    default_model: "llama3.2",
    api_type: "openai",
    free: true,
    models: ["llama3.2", "llama3.1", "mistral", "codellama", "phi3"]
  },
  perplexity: {
    name: "Perplexity",
    base_url: "https://api.perplexity.ai",
    default_model: "sonar",
    api_type: "openai",
    free: false,
    models: ["sonar", "sonar-pro", "sonar-reasoning"]
  },
  custom: {
    name: "Custom",
    base_url: "",
    default_model: "",
    api_type: "openai",
    free: true,
    custom: true,
    models: []
  }
};

module.exports = { PROVIDERS };