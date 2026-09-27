const express = require('express');
const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');
const { getDb } = require('../database');

const router = express.Router();
const JWT_SECRET = process.env.JWT_SECRET || 'dev-secret-change-in-production';
const JWT_EXPIRES_IN = '7d';
const EMAIL_VERIFICATION_EXPIRES_IN = '24h';
const PASSWORD_RESET_EXPIRES_IN = '1h';
const SALT_ROUNDS = 12;

// Rate limiting storage
const loginAttempts = new Map();
const MAX_LOGIN_ATTEMPTS = 5;
const LOGIN_LOCKOUT_TIME = 15 * 60 * 1000; // 15 minutes

/* ====================
   AUTH ROUTES
==================== */

// POST /auth/register
router.post('/register', async (req, res) => {
 try {
 const { email, username, password, displayName } = req.body;

 // Validation
 if (!email || !password) {
 return res.status(400).json({ error: 'Email and password are required' });
 }

 if (!username) {
 return res.status(400).json({ error: 'Username is required' });
 }

 if (password.length < 8) {
 return res.status(400).json({ error: 'Password must be at least 8 characters' });
 }

 if (!/^[a-zA-Z0-9_]{3,30}$/.test(username)) {
 return res.status(400).json({ error: 'Username must be 3-30 alphanumeric characters or underscores' });
 }

 if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
 return res.status(400).json({ error: 'Invalid email format' });
 }

 const db = getDb();

 // Check for existing user
 const existingUser = db.prepare('SELECT id FROM users WHERE email = ? OR username = ?').get(email, username);
 if (existingUser) {
 return res.status(409).json({ error: 'Email or username already exists' });
 }

 // Hash password
 const passwordHash = await bcrypt.hash(password, SALT_ROUNDS);

 // Generate verification token
 const verificationToken = require('crypto').randomBytes(32).toString('hex');
 const verificationTokenExpires = new Date(Date.now() + 24 * 60 * 60 * 1000);

 // Create user
 const result = db.prepare(`
 INSERT INTO users (email, username, display_name, password_hash, verification_token, verification_token_expires)
 VALUES (?, ?, ?, ?, ?, ?)
 `).run(email, username, displayName || username, passwordHash, verificationToken, verificationTokenExpires.toISOString());

 const userId = result.lastID;

 // Create default workspace
 db.prepare('INSERT INTO projects (owner_id, name, slug, description, workspace_id) VALUES (?, ?, ?, ?, ?)').run(
 userId,
 'Main Project',
 'main',
 'My first project workspace',
 'workspace-1'
 );

 res.status(201).json({
 success: true,
 user: { id: userId, email, username, displayName: displayName || username }
 });

 } catch (err) {
 console.error('Registration error:', err);
 res.status(500).json({ error: 'Registration failed' });
 }
});

// POST /auth/login
router.post('/login', async (req, res) => {
 try {
 const { emailOrUsername, password } = req.body;

 if (!emailOrUsername || !password) {
 return res.status(400).json({ error: 'Email/username and password are required' });
 }

 // Rate limiting check
 const clientIp = req.ip || req.connection.remoteAddress;
 const now = Date.now();

 if (loginAttempts.has(clientIp)) {
 const attempt = loginAttempts.get(clientIp);
 if (attempt.count >= MAX_LOGIN_ATTEMPTS && now - attempt.lastAttempt < LOGIN_LOCKOUT_TIME) {
 return res.status(429).json({ error: `Too many login attempts. Try again in ${Math.ceil((Login_ATTEMPTS_TIME - now + attempt.lastAttempt) / 1000)} seconds` });
 }
 }

 const db = getDb();
 const user = db.prepare('SELECT * FROM users WHERE email = ? OR username = ?').get(emailOrUsername, emailOrUsername);

 if (!user) {
 return res.status(401).json({ error: 'Invalid credentials' });
 }

 if (user.disabled_at) {
 return res.status(403).json({ error: 'Account is disabled' });
 }

 const validPassword = await bcrypt.compare(password, user.password_hash);
 if (!validPassword) {
 // Increment failed attempts
 const attempts = loginAttempts.get(clientIp) || { count: 0, lastAttempt: 0 };
 attempts.count++;
 attempts.lastAttempt = now;
 loginAttempts.set(clientIp, attempts);

 return res.status(401).json({ error: 'Invalid credentials' });
 }

 // Reset failed attempts on successful login
 loginAttempts.delete(clientIp);

 // Generate JWT
 const token = jwt.sign(
 { userId: user.id, email: user.email, username: user.username },
 JWT_SECRET,
 { expiresIn: JWT_EXPIRES_IN }
 );

 // Update last login
 db.prepare('UPDATE users SET last_login_at = ? WHERE id = ?').run(new Date().toISOString(), user.id);

 res.json({
 success: true,
 token,
 user: { id: user.id, email: user.email, username: user.username, displayName: user.display_name, emailVerified: user.email_verified }
 });

 } catch (err) {
 console.error('Login error:', err);
 res.status(500).json({ error: 'Login failed' });
 }
});

// POST /auth/logout
router.post('/logout', (req, res) => {
 const authHeader = req.headers.authorization;
 if (!authHeader || !authHeader.startsWith('Bearer ')) {
 return res.status(401).json({ error: 'No token provided' });
 }

 const token = authHeader.split(' ')[1];
 try {
 jwt.verify(token, JWT_SECRET);
 res.json({ success: true });
 } catch (err) {
 res.status(401).json({ error: 'Invalid token' });
 }
});

// GET /auth/me
router.get('/me', authenticateToken, (req, res) => {
 res.json({
 user: {
 id: req.user.id,
 email: req.user.email,
 username: req.user.username
 }
 });
});

module.exports = router;
module.exports.authenticateToken = authenticateToken;

function authenticateToken(req, res, next) {
 const authHeader = req.headers.authorization;
 if (!authHeader || !authHeader.startsWith('Bearer ')) {
 return res.status(401).json({ error: 'No token provided' });
 }

 const token = authHeader.split(' ')[1];
 try {
 const decoded = jwt.verify(token, JWT_SECRET);
 req.user = decoded;
 next();
 } catch (err) {
 res.status(401).json({ error: 'Invalid token' });
 }
}
