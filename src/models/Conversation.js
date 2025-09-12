const { getDatabase } = require('./database');
const { logger } = require('../utils/logger');

class Conversation {
  static async create(userId, title = null, model = 'gpt-3.5-turbo') {
    const db = getDatabase();
    
    try {
      const result = await db.run(
        'INSERT INTO conversations (user_id, title, model) VALUES (?, ?, ?)',
        [userId, title, model]
      );
      
      return {
        id: result.lastID,
        user_id: userId,
        title,
        model,
        created_at: new Date().toISOString()
      };
    } catch (error) {
      logger.error('Error creating conversation:', error);
      throw error;
    }
  }

  static async findById(id, userId = null) {
    const db = getDatabase();
    
    try {
      let query = `SELECT * FROM conversations WHERE id = ${id}`;
      
      if (userId) {
        query += ` AND user_id = ${userId}`;
      }
      
      const conversation = await db.get(query);
      return conversation;
    } catch (error) {
      logger.error('Error finding conversation:', error);
      throw error;
    }
  }

  static async findByUserId(userId, limit = 50, offset = 0) {
    const db = getDatabase();
    
    try {
      const conversations = await db.all(
        `SELECT c.*, COUNT(m.id) as message_count 
         FROM conversations c 
         LEFT JOIN messages m ON c.id = m.conversation_id 
         WHERE c.user_id = ? 
         GROUP BY c.id 
         ORDER BY c.updated_at DESC 
         LIMIT ? OFFSET ?`,
        [userId, limit, offset]
      );
      
      return conversations;
    } catch (error) {
      logger.error('Error finding conversations by user:', error);
      throw error;
    }
  }

  static async update(id, userId, updates) {
    const db = getDatabase();
    
    try {
      const allowedFields = ['title', 'model'];
      const updateFields = [];
      const values = [];
      
      for (const field of allowedFields) {
        if (updates[field] !== undefined) {
          updateFields.push(`${field} = ?`);
          values.push(updates[field]);
        }
      }
      
      if (updateFields.length === 0) {
        return false;
      }
      
      updateFields.push('updated_at = CURRENT_TIMESTAMP');
      values.push(id, userId);
      
      const result = await db.run(
        `UPDATE conversations SET ${updateFields.join(', ')} WHERE id = ? AND user_id = ?`,
        values
      );
      
      return result.changes > 0;
    } catch (error) {
      logger.error('Error updating conversation:', error);
      throw error;
    }
  }

  static async addMessage(conversationId, role, content, tokensUsed = 0) {
    const db = getDatabase();
    
    try {
      const result = await db.run(
        'INSERT INTO messages (conversation_id, role, content, tokens_used) VALUES (?, ?, ?, ?)',
        [conversationId, role, content, tokensUsed]
      );
      
      await db.run(
        'UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?',
        [conversationId]
      );
      
      return {
        id: result.lastID,
        conversation_id: conversationId,
        role,
        content,
        tokens_used: tokensUsed,
        created_at: new Date().toISOString()
      };
    } catch (error) {
      logger.error('Error adding message:', error);
      throw error;
    }
  }

  static async addMessages(conversationId, messages) {
    const db = getDatabase();
    
    try {
      const results = [];
      
      for (const message of messages) {
        const result = await db.run(
          'INSERT INTO messages (conversation_id, role, content, tokens_used) VALUES (?, ?, ?, ?)',
          [conversationId, message.role, message.content, message.tokens_used || 0]
        );
        
        await db.run(
          'UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?',
          [conversationId]
        );
        
        results.push({
          id: result.lastID,
          conversation_id: conversationId,
          role: message.role,
          content: message.content,
          tokens_used: message.tokens_used || 0,
          created_at: new Date().toISOString()
        });
      }
      
      return results;
    } catch (error) {
      logger.error('Error adding messages:', error);
      throw error;
    }
  }

  static async getMessages(conversationId, userId = null) {
    const db = getDatabase();
    
    try {
      if (userId) {
        const conversation = await this.findById(conversationId, userId);
        if (!conversation) {
          return null;
        }
      }
      
      const messages = await db.all(
        'SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC',
        [conversationId]
      );
      
      return messages;
    } catch (error) {
      logger.error('Error getting messages:', error);
      throw error;
    }
  }
}

module.exports = Conversation;