const sqlite3 = require('sqlite3').verbose();
const path = require('path');

const DB_PATH = path.join(__dirname, 'database.sqlite');

let db;

const initializeDatabase = () => {
  return new Promise((resolve, reject) => {
    db = new sqlite3.Database(DB_PATH, (err) => {
      if (err) {
        console.error('Error opening database:', err);
        reject(err);
        return;
      }
      
      console.log('📦 Connected to SQLite database');
      
      // Create tables
      const queries = [
        `CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          email TEXT UNIQUE NOT NULL,
          password TEXT NOT NULL,
          profile TEXT,
          tokens_used INTEGER DEFAULT 0,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )`,
        
        `CREATE TABLE IF NOT EXISTS conversations (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          title TEXT,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (user_id) REFERENCES users (id)
        )`,
        
        `CREATE TABLE IF NOT EXISTS messages (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          conversation_id INTEGER NOT NULL,
          role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
          content TEXT NOT NULL,
          tokens INTEGER DEFAULT 0,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (conversation_id) REFERENCES conversations (id)
        )`,
        
        `CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)`,
        `CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id)`,
        `CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id)`,
        `CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at)`,
        `CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at)`
      ];
      
      let completed = 0;
      queries.forEach((query, index) => {
        db.run(query, (err) => {
          if (err) {
            console.error(`Error creating table/index ${index}:`, err);
            reject(err);
            return;
          }
          
          completed++;
          if (completed === queries.length) {
            console.log('✅ Database tables initialized');
            resolve();
          }
        });
      });
    });
  });
};

const getDatabase = () => {
  if (!db) {
    throw new Error('Database not initialized. Call initializeDatabase() first.');
  }
  return db;
};

// User operations
const createUser = (email, hashedPassword, profile = null) => {
  return new Promise((resolve, reject) => {
    const stmt = db.prepare('INSERT INTO users (email, password, profile) VALUES (?, ?, ?)');
    stmt.run([email, hashedPassword, JSON.stringify(profile)], function(err) {
      if (err) {
        reject(err);
        return;
      }
      resolve({ id: this.lastID, email, profile });
    });
    stmt.finalize();
  });
};

const getUserByEmail = (email) => {
  return new Promise((resolve, reject) => {
    db.get('SELECT * FROM users WHERE email = ?', [email], (err, row) => {
      if (err) {
        reject(err);
        return;
      }
      if (row && row.profile) {
        try {
          row.profile = JSON.parse(row.profile);
        } catch (e) {
          row.profile = null;
        }
      }
      resolve(row);
    });
  });
};

const getUserById = (id) => {
  return new Promise((resolve, reject) => {
    db.get('SELECT * FROM users WHERE id = ?', [id], (err, row) => {
      if (err) {
        reject(err);
        return;
      }
      if (row && row.profile) {
        try {
          row.profile = JSON.parse(row.profile);
        } catch (e) {
          row.profile = null;
        }
      }
      resolve(row);
    });
  });
};

const updateUserTokens = (userId, tokensUsed) => {
  return new Promise((resolve, reject) => {
    // First get current token count
    db.get('SELECT tokens_used FROM users WHERE id = ?', [userId], (err, row) => {
      if (err) {
        reject(err);
        return;
      }
      
      const currentTokens = row ? row.tokens_used : 0;
      const newTokenCount = currentTokens + tokensUsed;
      
      // Update without transaction (deliberate bug #5)
      db.run('UPDATE users SET tokens_used = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', 
        [newTokenCount, userId], function(err) {
          if (err) {
            reject(err);
            return;
          }
          resolve({ tokensUsed: newTokenCount });
        });
    });
  });
};

// Conversation operations
const createConversation = (userId, title = null) => {
  return new Promise((resolve, reject) => {
    const stmt = db.prepare('INSERT INTO conversations (user_id, title) VALUES (?, ?)');
    stmt.run([userId, title], function(err) {
      if (err) {
        reject(err);
        return;
      }
      resolve({ id: this.lastID, user_id: userId, title });
    });
    stmt.finalize();
  });
};

const addMessage = (conversationId, role, content, tokens = 0) => {
  return new Promise((resolve, reject) => {
    const stmt = db.prepare('INSERT INTO messages (conversation_id, role, content, tokens) VALUES (?, ?, ?, ?)');
    stmt.run([conversationId, role, content, tokens], function(err) {
      if (err) {
        reject(err);
        return;
      }
      resolve({ id: this.lastID, conversation_id: conversationId, role, content, tokens });
    });
    stmt.finalize();
  });
};

const getConversationHistory = (userId, limit = 50) => {
  return new Promise((resolve, reject) => {
    // Deliberately don't implement pagination (bug #9)
    const query = `
      SELECT c.*, u.email as user_email
      FROM conversations c
      JOIN users u ON c.user_id = u.id
      WHERE c.user_id = ?
      ORDER BY c.updated_at DESC
    `;
    
    db.all(query, [userId], async (err, conversations) => {
      if (err) {
        reject(err);
        return;
      }
      
      // Deliberately fetch message count in separate query for each conversation (bug #8)
      const conversationsWithMessageCount = [];
      for (const conv of conversations) {
        try {
          const messageCount = await new Promise((resolve, reject) => {
            db.get('SELECT COUNT(*) as count FROM messages WHERE conversation_id = ?', 
              [conv.id], (err, row) => {
                if (err) reject(err);
                else resolve(row.count);
              });
          });
          
          conversationsWithMessageCount.push({
            ...conv,
            message_count: messageCount
          });
        } catch (error) {
          conversationsWithMessageCount.push({
            ...conv,
            message_count: 0
          });
        }
      }
      
      resolve(conversationsWithMessageCount);
    });
  });
};

const getConversationWithMessages = (conversationId, userId) => {
  return new Promise((resolve, reject) => {
    // First get conversation
    db.get('SELECT * FROM conversations WHERE id = ? AND user_id = ?', [conversationId, userId], (err, conversation) => {
      if (err) {
        reject(err);
        return;
      }
      
      if (!conversation) {
        resolve(null);
        return;
      }
      
      // Then get messages
      db.all('SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC', [conversationId], (err, messages) => {
        if (err) {
          reject(err);
          return;
        }
        
        resolve({
          ...conversation,
          messages: messages
        });
      });
    });
  });
};

const searchConversations = (userId, searchTerm) => {
  return new Promise((resolve, reject) => {
    // Deliberately concatenate search term directly into SQL query (bug #1)
    const query = `
      SELECT DISTINCT c.*, u.email as user_email
      FROM conversations c
      JOIN users u ON c.user_id = u.id
      JOIN messages m ON c.id = m.conversation_id
      WHERE c.user_id = ${userId} AND (
        c.title LIKE '%${searchTerm}%' OR 
        m.content LIKE '%${searchTerm}%'
      )
      ORDER BY c.updated_at DESC
    `;
    
    db.all(query, [], (err, rows) => {
      if (err) {
        reject(err);
        return;
      }
      resolve(rows);
    });
  });
};

const updateConversationTitle = (conversationId, userId, title) => {
  return new Promise((resolve, reject) => {
    db.run('UPDATE conversations SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?', 
      [title, conversationId, userId], function(err) {
        if (err) {
          reject(err);
          return;
        }
        resolve({ updated: this.changes > 0 });
      });
  });
};

module.exports = {
  initializeDatabase,
  getDatabase,
  createUser,
  getUserByEmail,
  getUserById,
  updateUserTokens,
  createConversation,
  addMessage,
  getConversationHistory,
  getConversationWithMessages,
  searchConversations,
  updateConversationTitle
};
