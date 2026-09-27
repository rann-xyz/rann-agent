// Middleware for workspace isolation and authorization
const { getDb } = require('../database');

/**
 * Ensures user can only access their own resources
 * Use as middleware: requires auth middleware first
 */
function enforceOwnership(modelType) {
 return (req, res, next) => {
 const db = getDb();
 const resourceId = req.params.id || req.body.id;
 const userId = req.user.userId;

 if (!resourceId) {
 return res.status(400).json({ error: 'Resource ID required' });
 }

 let query;
 switch (modelType) {
 case 'project':
 query = db.prepare('SELECT owner_id FROM projects WHERE id = ?');
 break;
 case 'agentSession':
 query = db.prepare('SELECT user_id FROM agent_sessions WHERE id = ?');
 break;
 case 'execution':
 query = db.prepare('SELECT user_id FROM execution_history WHERE id = ?');
 break;
 default:
 return res.status(400).json({ error: 'Invalid model type' });
 }

 const resource = query.get(resourceId);
 if (!resource) {
 return res.status(404).json({ error: 'Resource not found' });
 }

 if (resource.owner_id !== userId) {
 return res.status(403).json({ error: 'Access denied' });
 }

 next();
 };
}

/**
 * Validates workspace isolation
 * Ensures user's project belongs to their workspace
 */
function validateWorkspaceIntegrity(req, res, next) {
 const db = getDb();
 const { userId } = req.user;
 const projectId = req.params.projectId || req.body.projectId || req.query.projectId;

 if (!projectId) {
 return res.status(400).json({ error: 'Project ID required' });
 }

 const project = db.prepare('SELECT owner_id FROM projects WHERE id = ?').get(projectId);

 if (!project) {
 return res.status(404).json({ error: 'Project not found' });
 }

 if (project.owner_id !== userId) {
 return res.status(403).json({ error: 'Access denied to project' });
 }

 next();
}

/**
 * Session validation middleware
 */
function validateSession(req, res, next) {
 const authHeader = req.headers.authorization;
 if (!authHeader || !authHeader.startsWith('Bearer ')) {
 return res.status(401).json({ error: 'No session token' });
 }

 // Token validation is done in authenticateToken
 next();
}

/**
 * Workspace sandbox abstraction
 */
class WorkspaceSandbox {
 constructor(userId, projectId) {
 this.userId = userId;
 this.projectId = projectId;
 this.workspaceId = `workspace-${userId}-${projectId}`;
 this.status = 'stopped';
 }

 async create() {
 // Create isolated workspace directory
 const fs = require('fs');
 const path = require('path');
 const workspaceDir = path.join(process.env.WORKSPACE_ROOT || './workspaces', this.workspaceId);

 if (!fs.existsSync(workspaceDir)) {
 fs.mkdirSync(workspaceDir, { recursive: true });
 }

 this.status = 'ready';
 return { success: true, workspaceId: this.workspaceId };
 }

 async start() {
 if (this.status === 'stopped' || this.status === 'ready') {
 this.status = 'running';
 this.startTime = new Date().toISOString();
 return { success: true };
 }
 return { success: false, error: 'Cannot start sandbox in current state' };
 }

 async stop() {
 this.status = 'stopped';
 this.endTime = new Date().toISOString();
 return { success: true };
 }

 async destroy() {
 await this.stop();
 this.status = 'destroyed';
 return { success: true };
 }

 async execute(command, timeout = 30000) {
 if (this.status !== 'running') {
 return { error: 'Sandbox not running' };
 }

 // Environment isolation
 const env = {
 PATH: process.env.PATH,
 HOME: `/workspaces/${this.workspaceId}`,
 WORKSPACE: `/workspaces/${this.workspaceId}`
 };

 // Execute with limits
 return {
 success: true,
 command,
 output: 'Simulated execution - implement with Docker/container runtime',
 exitCode: 0
 };
 }

 getStatus() {
 return {
 status: this.status,
 userId: this.userId,
 projectId: this.projectId,
 workspaceId: this.workspaceId,
 startedAt: this.startTime
 };
 }
}

module.exports = {
 enforceOwnership,
 validateWorkspaceIntegrity,
 validateSession,
 WorkspaceSandbox
 };
