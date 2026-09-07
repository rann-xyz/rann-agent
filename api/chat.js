const { PROVIDERS } = require('../providers.js');

function setCorsHeaders(res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
}

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

async function chatOpenAI(api_key, base_url, model, messages) {
  const response = await fetch(`${base_url}/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${api_key}`,
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      'Accept': 'application/json'
    },
    body: JSON.stringify({
      model,
      messages,
      max_tokens: 2000,
      temperature: 0.7,
      stream: true
    })
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`API Error ${response.status}: ${err.slice(0, 200)}`);
  }

  return response;
}

async function chatAnthropic(api_key, base_url, model, messages) {
  // Anthropic uses non-streaming /messages endpoint in serverless
  const msgs = messages.filter(m => m.role !== 'system').map(m => ({
    role: m.role,
    content: m.content
  }));

  const response = await fetch(`${base_url}/v1/messages`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': api_key,
      'anthropic-version': '2023-06-01',
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      'Accept': 'application/json'
    },
    body: JSON.dumps({
      model,
      messages: msgs,
      max_tokens: 4096
    })
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`API Error ${response.status}: ${err.slice(0, 200)}`);
  }

  const result = await response.json();
  return result.content[0].text;
}

async function chatGemini(api_key, base_url, model, messages) {
  const contents = messages
    .filter(m => m.role !== 'system')
    .map(msg => ({
      role: msg.role === 'assistant' ? 'model' : 'user',
      parts: [{ text: msg.content }]
    }));

  const response = await fetch(
    `${base_url}/models/${model}:generateContent?key=${api_key}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contents,
        generationConfig: { maxOutputTokens: 2000, temperature: 0.7 }
      })
    }
  );

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`API Error ${response.status}: ${err.slice(0, 200)}`);
  }

  const result = await response.json();
  return result.candidates[0].content.parts[0].text;
}

module.exports = async function handler(req, res) {
  setCorsHeaders(res);

  if (req.method === 'OPTIONS') {
    res.status(200).end();
    return;
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  let data;
  try {
    data = await req.json();
  } catch {
    return res.status(400).json({ error: 'Invalid JSON body' });
  }

  const { message, history = [], provider = 'groq', model: modelOverride, api_key, base_url: customBaseUrl } = data;

  if (!message) {
    return res.status(400).json({ error: 'Message is required' });
  }

  if (!api_key) {
    return res.status(400).json({ error: 'API key is required. Add key in Settings.' });
  }

  const prov = getProviderConfig(provider, customBaseUrl);
  const base_url = prov.base_url;
  const model = modelOverride || prov.default_model;

  if (!base_url) {
    return res.status(400).json({ error: 'Base URL is required. Configure a provider or use Custom.' });
  }

  const systemMessage = { role: 'system', content: 'You are RANN Agent. Be concise and helpful. Format code with triple backticks.' };
  const messages = [systemMessage, ...history, { role: 'user', content: message }];

  const startTime = Date.now();

  try {
    if (prov.api_type === 'anthropic') {
      // Anthropic: non-streaming
      const content = await chatAnthropic(api_key, base_url, model, messages);
      const latency_ms = Date.now() - startTime;
      return res.status(200).json({
        response: content,
        tokens: 0,
        model,
        latency_ms,
        error: null
      });
    }

    if (prov.api_type === 'gemini') {
      // Gemini: non-streaming
      const content = await chatGemini(api_key, base_url, model, messages);
      const latency_ms = Date.now() - startTime;
      return res.status(200).json({
        response: content,
        tokens: 0,
        model,
        latency_ms,
        error: null
      });
    }

    // OpenAI-compatible: streaming
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');

    const response = await chatOpenAI(api_key, base_url, model, messages);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let fullContent = '';
    let tokenCount = 0;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      for (const line of chunk.split('\n')) {
        if (line.startsWith('data: ')) {
          const dataStr = line.slice(6).trim();
          if (dataStr === '[DONE]') {
            res.end();
            const latency_ms = Date.now() - startTime;
            return;
          }
          try {
            const parsed = JSON.parse(dataStr);
            const content = parsed.choices?.[0]?.delta?.content || '';
            if (content) {
              fullContent += content;
              tokenCount++;
              res.write(`data: ${JSON.stringify({ content })}\n\n`);
            }
          } catch (e) {
            // Skip malformed JSON
          }
        }
      }
    }

    res.end();
    const latency_ms = Date.now() - startTime;
    res.write(`data: ${JSON.stringify({
      done: true,
      response: fullContent,
      tokens: tokenCount,
      model,
      latency_ms
    })}\n\n`);

  } catch (err) {
    const latency_ms = Date.now() - startTime;
    console.error('Chat error:', err);
    return res.status(500).json({
      response: null,
      tokens: 0,
      model,
      latency_ms,
      error: err.message
    });
  }
};