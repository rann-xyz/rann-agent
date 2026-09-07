// Provider configurations — matches web_api.py PROVIDERS
const PROVIDERS = {
  groq: {
    name: "Groq",
    base_url: "https://api.groq.com/openai/v1",
    default_model: "llama-3.3-70b-versatile",
    api_type: "openai",
    free: true,
    models: [
      "llama-3.3-70b-versatile",
      "llama-3.1-70b-versatile",
      "llama-3.1-8b-instant",
      "llama-3.2-1b-preview",
      "llama-3.2-3b-preview",
      "llama-3.2-11b-preview",
      "mixtral-8x7b-32768",
      "gemma-7b-it",
      "qwen-2.5-72b-instruct",
      "qwq-32b-preview"
    ]
  },
  deepseek: {
    name: "DeepSeek",
    base_url: "https://api.deepseek.com/v1",
    default_model: "deepseek-chat",
    api_type: "openai",
    free: true,
    models: ["deepseek-chat", "deepseek-coder", "deepseek-reasoner", "deepseek-v3"]
  },
  openai: {
    name: "OpenAI",
    base_url: "https://api.openai.com/v1",
    default_model: "gpt-4o",
    api_type: "openai",
    free: false,
    models: ["gpt-4o", "gpt-4o-mini", "gpt-4o-audio-preview", "gpt-4-turbo", "gpt-3.5-turbo", "o1-preview", "o1-mini", "o1", "o1-pro"]
  },
  anthropic: {
    name: "Anthropic",
    base_url: "https://api.anthropic.com/v1",
    default_model: "claude-sonnet-4-20250514",
    api_type: "anthropic",
    free: false,
    models: ["claude-sonnet-4-20250514", "claude-opus-4-20250514", "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-5-sonnet-latest", "claude-sonnet-4-latest"]
  },
  gemini: {
    name: "Google Gemini",
    base_url: "https://generativelanguage.googleapis.com/v1beta",
    default_model: "gemini-2.0-flash-exp",
    api_type: "gemini",
    free: true,
    models: ["gemini-2.0-flash-exp", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-flash-8b", "gemini-1.5-pro", "gemini-1.0-pro", "gemini-exp-1206", "gemini-2.5-flash-preview-05-20"]
  },
  ollama: {
    name: "Ollama",
    base_url: "http://localhost:11434/v1",
    default_model: "llama3.3",
    api_type: "openai",
    free: true,
    models: ["llama3.3", "llama3.2", "llama3.1", "llama3", "mistral", "mistral-nemo", "codellama", "codellama:70b", "phi3", "phi3-medium", "qwen2.5", "qwen2.5-coder", "deepseek-v2", "gemma2", "starcoder2"]
  },
  perplexity: {
    name: "Perplexity",
    base_url: "https://api.perplexity.ai",
    default_model: "sonar",
    api_type: "openai",
    free: false,
    models: ["sonar", "sonar-pro", "sonar-reasoning", "sonar-reasoning-pro", "sonar-reasoning-20250507"]
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