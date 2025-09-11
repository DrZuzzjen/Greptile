const sqlite3 = require('sqlite3').verbose();
const path = require('path');

class Database {
  constructor() {
    this.db = null;
  }

  async connect() {
    return new Promise((resolve, reject) => {
      this.db = new sqlite3.Database('openai_proxy.db', (err) => {
        if (err) {
          console.error('Error opening database:', err);
          reject(err);
        } else {
          console.log('Connected to SQLite database');
          this.initTables()
            .then(() => resolve())
            .catch(reject);
        }
      });
    });
  }

  async initTables() {
    const createUsersTable = `
      CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username VARCHAR(255) UNIQUE NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL,
        password VARCHAR(255) NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        token_usage INTEGER DEFAULT 0
      )
    `;

    const createProfilesTable = `
      CREATE TABLE IF NOT EXISTS profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name VARCHAR(255),
        bio TEXT,
        avatar_url VARCHAR(500),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
      )
    `;

    const createConversationsTable = `
      CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title VARCHAR(500),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
      )
    `;

    const createMessagesTable = `
      CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER NOT NULL,
        role VARCHAR(50) NOT NULL,
        content TEXT NOT NULL,
        tokens_used INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
      )
    `;

    return new Promise((resolve, reject) => {
      this.db.serialize(() => {
        this.db.run(createUsersTable);
        this.db.run(createProfilesTable);
        this.db.run(createConversationsTable);
        this.db.run(createMessagesTable, (err) => {
          if (err) {
            reject(err);
          } else {
            console.log('Database tables initialized');
            resolve();
          }
        });
      });
    });
  }

  async createUser(username, email, hashedPassword) {
    return new Promise((resolve, reject) => {
      const stmt = this.db.prepare(`
        INSERT INTO users (username, email, password) 
        VALUES (?, ?, ?)
      `);
      
      stmt.run([username, email, hashedPassword], function(err) {
        if (err) {
          reject(err);
        } else {
          resolve({ id: this.lastID, username, email });
        }
      });
      
      stmt.finalize();
    });
  }

  async getUserByEmail(email) {
    return new Promise((resolve, reject) => {
      this.db.get(
        'SELECT * FROM users WHERE email = ?',
        [email],
        (err, row) => {
          if (err) {
            reject(err);
          } else {
            resolve(row);
          }
        }
      );
    });
  }

  async getUserById(id) {
    return new Promise((resolve, reject) => {
      this.db.get(
        'SELECT u.*, p.name, p.bio, p.avatar_url FROM users u LEFT JOIN profiles p ON u.id = p.user_id WHERE u.id = ?',
        [id],
        (err, row) => {
          if (err) {
            reject(err);
          } else {
            if (row) {
              // Structure the user object with profile data
              const user = {
                id: row.id,
                username: row.username,
                email: row.email,
                password: row.password,
                created_at: row.created_at,
                token_usage: row.token_usage
              };
              
              if (row.name || row.bio || row.avatar_url) {
                user.profile = {
                  name: row.name,
                  bio: row.bio,
                  avatar_url: row.avatar_url
                };
              }
              
              resolve(user);
            } else {
              resolve(null);
            }
          }
        }
      );
    });
  }

  async updateTokenUsage(userId, tokensUsed) {
    return new Promise((resolve, reject) => {
      // Use atomic update to prevent race conditions
      this.db.run(
        'UPDATE users SET token_usage = token_usage + ? WHERE id = ?',
        [tokensUsed, userId],
        function(err) {
          if (err) {
            reject(err);
          } else {
            // Get the updated value
            this.db.get(
              'SELECT token_usage FROM users WHERE id = ?',
              [userId],
              (err, row) => {
                if (err) {
                  reject(err);
                } else {
                  resolve(row ? row.token_usage : 0);
                }
              }
            );
          }
        }
      );
    });
  }

  async createConversation(userId, title) {
    return new Promise((resolve, reject) => {
      const stmt = this.db.prepare(`
        INSERT INTO conversations (user_id, title) 
        VALUES (?, ?)
      `);
      
      stmt.run([userId, title], function(err) {
        if (err) {
          reject(err);
        } else {
          resolve({ id: this.lastID, user_id: userId, title });
        }
      });
      
      stmt.finalize();
    });
  }

  async addMessage(conversationId, role, content, tokensUsed = 0) {
    return new Promise((resolve, reject) => {
      const stmt = this.db.prepare(`
        INSERT INTO messages (conversation_id, role, content, tokens_used) 
        VALUES (?, ?, ?, ?)
      `);
      
      stmt.run([conversationId, role, content, tokensUsed], function(err) {
        if (err) {
          reject(err);
        } else {
          resolve({ 
            id: this.lastID, 
            conversation_id: conversationId, 
            role, 
            content, 
            tokens_used: tokensUsed 
          });
        }
      });
      
      stmt.finalize();
    });
  }

  async getConversationsByUser(userId) {
    return new Promise((resolve, reject) => {
      this.db.all(
        `SELECT c.*, COUNT(m.id) as message_count 
         FROM conversations c 
         LEFT JOIN messages m ON c.id = m.conversation_id 
         WHERE c.user_id = ? 
         GROUP BY c.id 
         ORDER BY c.updated_at DESC`,
        [userId],
        (err, rows) => {
          if (err) {
            reject(err);
          } else {
            resolve(rows);
          }
        }
      );
    });
  }

  async getMessageCountForConversation(conversationId) {
    return new Promise((resolve, reject) => {
      this.db.get(
        'SELECT COUNT(*) as count FROM messages WHERE conversation_id = ?',
        [conversationId],
        (err, row) => {
          if (err) {
            reject(err);
          } else {
            resolve(row ? row.count : 0);
          }
        }
      );
    });
  }

  async searchConversations(userId, searchTerm) {
    return new Promise((resolve, reject) => {
      // Use parameterized queries to prevent SQL injection
      const query = `
        SELECT DISTINCT c.* 
        FROM conversations c 
        JOIN messages m ON c.id = m.conversation_id 
        WHERE c.user_id = ? 
        AND (c.title LIKE ? OR m.content LIKE ?)
        ORDER BY c.updated_at DESC
      `;
      
      const searchPattern = `%${searchTerm}%`;
      this.db.all(query, [userId, searchPattern, searchPattern], (err, rows) => {
        if (err) {
          reject(err);
        } else {
          resolve(rows);
        }
      });
    });
  }

  async getConversationMessages(conversationId) {
    return new Promise((resolve, reject) => {
      this.db.all(
        'SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC',
        [conversationId],
        (err, rows) => {
          if (err) {
            reject(err);
          } else {
            resolve(rows);
          }
        }
      );
    });
  }

  async close() {
    return new Promise((resolve) => {
      if (this.db) {
        this.db.close((err) => {
          if (err) {
            console.error('Error closing database:', err);
          } else {
            console.log('Database connection closed');
          }
          resolve();
        });
      } else {
        resolve();
      }
    });
  }
}

module.exports = new Database();
