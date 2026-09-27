const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

const dbPath = process.env.DATABASE_PATH || path.join(__dirname, '..', 'rann.db');
const schemaPath = path.join(__dirname, 'schema.sql');

let db;

function initDatabase() {
 try {
 db = new Database(dbPath);
 console.log('Database connected:', dbPath);

 // Run schema
 const schema = fs.readFileSync(schemaPath, 'utf8');
 db.exec(schema);
 console.log('Schema initialized');

 return db;
 } catch (err) {
 console.error('Database initialization failed:', err.message);
 process.exit(1);
 }
}

function getDb() {
 if (!db) {
 initDatabase();
 }
 return db;
}

// Close database on exit
process.on('SIGINT', () => {
 if (db) db.close();
 process.exit(0);
});

module.exports = { getDb, initDatabase };
