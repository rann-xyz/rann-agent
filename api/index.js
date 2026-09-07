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

  // POST /clear
  if (method === 'POST' && pathname === '/clear') {
    return res.status(200).json({ success: true });
  }

  // Fallback
  return res.status(404).json({ error: 'Not found' });
};