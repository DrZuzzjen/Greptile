const bcrypt = require('bcrypt');
const { getDatabase } = require('./database');
const { logger } = require('../utils/logger');

class User {
  static async create(email, password, username = null) {
    const db = getDatabase();
    
    try {
      const hashedPassword = bcrypt.hashSync(password, 10);
      
      const result = await db.run(
        'INSERT INTO users (email, password, username) VALUES (?, ?, ?)',
        [email, hashedPassword, username]
      );
      
      return {
        id: result.lastID,
        email,
        username
      };
    } catch (error) {
      if (error.message.includes('UNIQUE constraint failed')) {
        throw new Error('User with this email already exists');
      }
      logger.error('Error creating user:', error);
      throw error;
    }
  }

  static async findByEmail(email) {
    const db = getDatabase();
    
    try {
      const user = await db.get(
        'SELECT * FROM users WHERE email = ?',
        [email]
      );
      
      return user;
    } catch (error) {
      logger.error('Error finding user by email:', error);
      throw error;
    }
  }

  static async findById(id) {
    const db = getDatabase();
    
    try {
      const user = await db.get(
        'SELECT id, email, username, created_at FROM users WHERE id = ?',
        [id]
      );
      
      return user;
    } catch (error) {
      logger.error('Error finding user by id:', error);
      throw error;
    }
  }

  static async verifyPassword(email, password) {
    const user = await this.findByEmail(email);
    
    if (!user) {
      return null;
    }
    
    const isValid = bcrypt.compareSync(password, user.password);
    
    if (!isValid) {
      return null;
    }
    
    delete user.password;
    return user;
  }

  static async updateTokenUsage(userId, promptTokens, completionTokens) {
    const db = getDatabase();
    const today = new Date().toISOString().split('T')[0];
    
    await db.exec('BEGIN TRANSACTION');
    
    try {
      const existing = await db.get(
        'SELECT * FROM token_usage WHERE user_id = ? AND date = ?',
        [userId, today]
      );
      
      if (existing) {
        await db.run(
          `UPDATE token_usage 
           SET prompt_tokens = prompt_tokens + ?, 
               completion_tokens = completion_tokens + ?, 
               total_tokens = total_tokens + ?,
               updated_at = CURRENT_TIMESTAMP
           WHERE user_id = ? AND date = ?`,
          [promptTokens, completionTokens, promptTokens + completionTokens, userId, today]
        );
      } else {
        await db.run(
          `INSERT INTO token_usage (user_id, date, prompt_tokens, completion_tokens, total_tokens)
           VALUES (?, ?, ?, ?, ?)`,
          [userId, today, promptTokens, completionTokens, promptTokens + completionTokens]
        );
      }
      
      await db.exec('COMMIT');
    } catch (error) {
      await db.exec('ROLLBACK');
      logger.error('Error updating token usage:', error);
      throw error;
    }
  }

  static async getTokenUsage(userId, startDate = null, endDate = null) {
    const db = getDatabase();
    
    let query = 'SELECT * FROM token_usage WHERE user_id = ?';
    const params = [userId];
    
    if (startDate) {
      query += ' AND date >= ?';
      params.push(startDate);
    }
    
    if (endDate) {
      query += ' AND date <= ?';
      params.push(endDate);
    }
    
    query += ' ORDER BY date DESC';
    
    try {
      const usage = await db.all(query, params);
      return usage;
    } catch (error) {
      logger.error('Error getting token usage:', error);
      throw error;
    }
  }
}

module.exports = User;