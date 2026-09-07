const { PROVIDERS } = require('../providers.js');

function setCorsHeaders(res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
}

module.exports = async function handler(req, res) {
  setCorsHeaders(res);

  if (req.method === 'OPTIONS') {
    res.status(200).end();
    return;
  }

  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const result = [];
  for (const [name, prov] of Object.entries(PROVIDERS)) {
    result.push({
      id: name,
      name: prov.name,
      base_url: prov.base_url,
      default_model: prov.default_model,
      api_type: prov.api_type,
      free: prov.free,
      has_key: false // localStorage check is done client-side
    });
  }

  return res.status(200).json(result);
};