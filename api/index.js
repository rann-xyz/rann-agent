const { PROVIDERS } = require('../providers.js');

function setCorsHeaders(res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
}

function handleOptions(res) {
  setCorsHeaders(res);
  res.status(200).end();
}

async function getBody(req) {
  // req can be Node.js IncomingMessage or Vercel Request
  const contentType = req.headers ? (req.headers['content-type'] || '') : (req.get('content-type') || '');
  if (contentType && !contentType.includes('application/json')) {
    throw new Error('Content-Type must be application/json');
  }
  let text;
  if (typeof req.text === 'function') {
    // Vercel Request object
    text = await req.text();
  } else if (Buffer.isBuffer(req.body)) {
    text = req.body.toString();
  } else if (typeof req.body === 'string') {
    text = req.body;
  } else if (req.body && typeof req.body.pipe === 'function') {
    // Node.js readable stream
    text = await new Promise((resolve, reject) => {
      const chunks = [];
      req.body.on('data', chunk => chunks.push(chunk));
      req.body.on('end', () => resolve(Buffer.concat(chunks).toString()));
      req.body.on('error', reject);
    });
  } else if (typeof req.on === 'function') {
    // Raw Node.js IncomingMessage — read directly from req
    text = await new Promise((resolve, reject) => {
      const chunks = [];
      req.on('data', chunk => chunks.push(chunk));
      req.on('end', () => resolve(Buffer.concat(chunks).toString()));
      req.on('error', reject);
    });
  } else {
    throw new Error('Unable to read request body');
  }
  if (!text || !text.trim()) {
    throw new Error('Request body is empty');
  }
  try {
    return JSON.parse(text);
  } catch {
    throw new Error('Invalid JSON body');
  }
}

module.exports = async function handler(req, res) {
  setCorsHeaders(res);

  if (req.method === 'OPTIONS') {
    handleOptions(res);
    return;
  }

  // pathname is /api/xxx (Vercel) or /xxx (local), normalize to /xxx
  const rawPath = req.nextUrl ? req.nextUrl.pathname : (req.url || '/').split('?')[0];
  const pathname = rawPath.startsWith('/api') ? rawPath.slice(4) : rawPath;
  const method = req.method;

  // GET /providers  (mapped to /api/providers)
  if (method === 'GET' && pathname === '/providers') {
    const result = [];
    for (const [name, prov] of Object.entries(PROVIDERS)) {
      result.push({
        id: name,
        name: prov.name,
        base_url: prov.base_url,
        default_model: prov.default_model,
        free: prov.free,
        api_type: prov.api_type,
        has_key: false // client-side check via localStorage
      });
    }
    return res.status(200).json(result);
  }

  // GET /config
  if (method === 'GET' && pathname === '/config') {
    return res.status(200).json({
      provider: 'groq',
      model: PROVIDERS.groq.default_model
    });
  }

  // GET /status
  if (method === 'GET' && pathname === '/status') {
    const providers = {};
    for (const [name, prov] of Object.entries(PROVIDERS)) {
      providers[name] = {
        has_key: false, // client sets API key in localStorage
        free: prov.free
      };
    }
    return res.status(200).json({
      status: 'online',
      version: '1.0.0',
      configured_providers: [],
      providers
    });
  }

  // POST /chat
  if (method === 'POST' && pathname === '/chat') {
    try {
      const data = await getBody(req);
      const { message, history = [], provider = 'groq', model: modelOverride, api_key, base_url: customBaseUrl } = data;

      if (!message) {
        return res.status(400).json({ error: 'Message is required' });
      }

      const prov = getProviderConfig(provider, customBaseUrl);
      const base_url = prov.base_url;
      const model = modelOverride || prov.default_model;

      if (!base_url) {
        return res.status(400).json({ error: 'Base URL is required. Configure a provider or use Custom.' });
      }

      // If api_key starts with 'free_' it's a placeholder — no real key provided.
      // Try anyway; API will return 401 and we'll return a friendly error.
      // Otherwise require the real key.
      const isPlaceholder = api_key && api_key.startsWith('free_');
      if (!api_key || isPlaceholder) {
        // Try the call without key (will fail with auth error, we return friendly message)
        api_key = api_key || 'placeholder';
      }

      const systemMessage = { role: 'system', content: 'You are RANN Agent. Be concise and helpful. Format code with triple backticks.' };
      const messages = [systemMessage, ...history, { role: 'user', content: message }];

      const startTime = Date.now();

      if (prov.api_type === 'anthropic') {
        const content = await chatAnthropic(api_key, base_url, model, messages);
        return res.status(200).json({ response: content, tokens: 0, model, latency_ms: Date.now() - startTime, error: null });
      }

      if (prov.api_type === 'gemini') {
        const content = await chatGemini(api_key, base_url, model, messages);
        return res.status(200).json({ response: content, tokens: 0, model, latency_ms: Date.now() - startTime, error: null });
      }

      // OpenAI-compatible: non-streaming
      const response = await chatOpenAI(api_key, base_url, model, messages, false);
      const result = await response.json();
      const content = result.choices?.[0]?.message?.content || '';
      return res.status(200).json({ response: content, tokens: result.usage?.total_tokens || 0, model, latency_ms: Date.now() - startTime, error: null });

    } catch (err) {
      const msg = err.message || '';
      // Return friendly error for auth failures (no real API key)
      if (msg.includes('401') || msg.includes('403') || msg.includes('invalid_api_key') || msg.includes('Incorrect API key')) {
        const providerName = req.headers.host || 'this provider';
        return res.status(401).json({
          error: `API key required for ${providerName}. Get a free key at console.groq.com (Groq), platform.deepseek.com (DeepSeek), or aiwstudio.google.com (Gemini). Add it in Settings.`
        });
      }
      return res.status(400).json({ error: err.message });
    }
    return;
  }

  // POST /clear
  if (method === 'POST' && pathname === '/clear') {
    return res.status(200).json({ success: true });
  }

  // POST /set_key — store provider API key (client-side only, just confirms receipt)
  if (method === 'POST' && pathname === '/set_key') {
    try {
      const data = await getBody(req);
      const { provider, api_key, model, base_url } = data;
      if (!provider || !api_key) {
        return res.status(400).json({ error: 'provider and api_key are required' });
      }
      // Vercel serverless: no persistent storage, just validate key format
      return res.status(200).json({ success: true, provider });
    } catch (err) {
      return res.status(400).json({ error: err.message });
    }
  }

  // GET /key/:provider — check if key is set (client-side check)
  if (method === 'GET' && pathname.startsWith('/key/')) {
    const prov = pathname.slice(5);
    return res.status(200).json({ has_key: false, provider: prov });
  }

  // Fallback
  return res.status(404).json({ error: `Not found: ${pathname}` });
};

function getProviderConfig(provider, base_url) {
  if (provider === 'custom' && base_url) {
    return {
      name: 'Custom',
      base_url: base_url.replace(/\/$/, ''),
      default_model: '',
      api_type: 'openai'
    };
  }
  return PROVIDERS[provider] || PROVIDERS.groq;
}

async function chatOpenAI(api_key, base_url, model, messages, stream = true) {
  const response = await fetch(`${base_url}/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${api_key}`,
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      'Accept': 'application/json'
    },
    body: JSON.stringify({ model, messages, max_tokens: 2000, temperature: 0.7, stream })
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`API Error ${response.status}: ${err.slice(0, 200)}`);
  }

  return response;
}

async function chatAnthropic(api_key, base_url, model, messages) {
  const msgs = messages.filter(m => m.role !== 'system').map(m => ({ role: m.role, content: m.content }));

  const response = await fetch(`${base_url}/v1/messages`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': api_key,
      'anthropic-version': '2023-06-01',
      'User-Agent': 'Mozilla/5.0',
      'Accept': 'application/json'
    },
    body: JSON.stringify({ model, messages: msgs, max_tokens: 4096 })
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`API Error ${response.status}: ${err.slice(0, 200)}`);
  }

  const result = await response.json();
  return result.content[0].text;
}

async function chatGemini(api_key, base_url, model, messages) {
  const contents = messages.filter(m => m.role !== 'system').map(msg => ({
    role: msg.role === 'assistant' ? 'model' : 'user',
    parts: [{ text: msg.content }]
  }));

  const response = await fetch(`${base_url}/models/${model}:generateContent?key=${api_key}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ contents, generationConfig: { maxOutputTokens: 2000, temperature: 0.7 } })
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`API Error ${response.status}: ${err.slice(0, 200)}`);
  }

  const result = await response.json();
  return result.candidates[0].content.parts[0].text;
}