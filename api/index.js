const express = require('express');
const cors = require('cors');
const { PROVIDERS } = require('./providers');
const { getDb } = require('./database/index');

// Initialize database on startup
getDb();

const app = express();

// CORS middleware
app.use(cors({
 origin: process.env.CORS_ORIGIN || '*',
 credentials: true
}));

// Body parser
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

// Mount auth routes
const authRoutes = require('./routes/auth');
app.use('/auth', authRoutes);

// Existing routes...
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
 const contentType = req.headers ? (req.headers['content-type'] || '') : (req.get('content-type') || '');
 if (contentType && !contentType.includes('application/json')) {
 throw new Error('Content-Type must be application/json');
 }
 let text;
 if (typeof req.text === 'function') {
 text = await req.text();
 } else if (Buffer.isBuffer(req.body)) {
 text = req.body.toString();
 } else if (typeof req.body === 'string') {
 text = req.body;
 } else if (req.body && typeof req.body.pipe === 'function') {
 text = await new Promise((resolve, reject) => {
 const chunks = [];
 req.body.on('data', chunk => chunks.push(chunk));
 req.body.on('end', () => resolve(Buffer.concat(chunks).toString()));
 req.body.on('error', reject);
 });
 } else if (typeof req.on === 'function') {
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

 const rawPath = req.nextUrl ? req.nextUrl.pathname : (req.url || '/').split('?')[0];
 const pathname = rawPath.startsWith('/api') ? rawPath.slice(4) : rawPath;
 const method = req.method;

 // If path starts with /auth, it's handled by mounted router
 if (pathname.startsWith('/auth')) {
 return authHandler(req, res);
 }

 // Existing routes...
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
 has_key: false
 });
 }
 return res.status(200).json(result);
 }

 if (method === 'GET' && pathname === '/config') {
 return res.status(200).json({
 provider: 'groq',
 model: PROVIDERS.groq.default_model
 });
 }

 if (method === 'GET' && pathname === '/status') {
 const providers = {};
 for (const [name, prov] of Object.entries(PROVIDERS)) {
 providers[name] = {
 has_key: false,
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

 // Login/Register routes will be handled by the mounted auth router
 // ... rest of existing routes

 return res.status(404).json({ error: `Not found: ${pathname}` });
};

async function authHandler(req, res) {
 try {
 const router = require('./routes/auth');
 await router(req, res);
 } catch (err) {
 console.error('Auth handler error:', err);
 res.status(500).json({ error: 'Auth processing failed' });
 }
}
