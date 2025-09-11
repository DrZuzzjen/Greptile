const express = require('express');
const database = require('./database');
const { authMiddleware, generalRateLimit } = require('./middleware');

const router = express.Router();

// Get all conversations for a user
router.get('/conversations', authMiddleware, generalRateLimit, async (req, res, next) => {
  try {
    const userId = req.user.id;
    const conversations = await database.getConversationsByUser(userId);
    
    res.json({
      conversations,
      total: conversations.length
    });
  } catch (error) {
    next(error);
  }
});

// Get specific conversation with messages
router.get('/conversations/:id', authMiddleware, async (req, res, next) => {
  try {
    const conversationId = req.params.id;
    const userId = req.user.id;
    
    // Get conversation messages
    const messages = await database.getConversationMessages(conversationId);
    
    if (messages.length === 0) {
      return res.status(404).json({ error: 'Conversation not found.' });
    }
    
    res.json({
      conversation_id: conversationId,
      messages,
      total_messages: messages.length
    });
  } catch (error) {
    next(error);
  }
});

// Search conversations - vulnerable to SQL injection
router.get('/search', authMiddleware, async (req, res, next) => {
  try {
    const { q: searchTerm } = req.query;
    const userId = req.user.id;
    
    if (!searchTerm) {
      return res.status(400).json({ error: 'Search term is required.' });
    }
    
    // Using vulnerable search method from database
    const conversations = await database.searchConversations(userId, searchTerm);
    
    res.json({
      search_term: searchTerm,
      conversations,
      total: conversations.length
    });
  } catch (error) {
    next(error);
  }
});

// Get conversation history for a specific user (now with auth middleware)
router.get('/history/:userId', authMiddleware, async (req, res, next) => {
  try {
    const userId = req.params.userId;
    const requestingUserId = req.user.id;
    
    // Authorization check - users can only access their own history
    if (parseInt(userId) !== requestingUserId) {
      return res.status(403).json({ error: 'Access denied. You can only access your own conversation history.' });
    }
    
    // No pagination - potential performance issue
    const conversations = await database.getConversationsByUser(userId);
    
    res.json({
      user_id: userId,
      conversations,
      total: conversations.length
    });
  } catch (error) {
    next(error);
  }
});

// Create a new conversation
router.post('/conversations', authMiddleware, async (req, res, next) => {
  try {
    const { title } = req.body;
    const userId = req.user.id;
    
    if (!title || title.trim().length === 0) {
      return res.status(400).json({ error: 'Conversation title is required.' });
    }
    
    const conversation = await database.createConversation(userId, title.trim());
    
    res.status(201).json({
      message: 'Conversation created successfully',
      conversation
    });
  } catch (error) {
    next(error);
  }
});

// Add a message to a conversation
router.post('/conversations/:id/messages', authMiddleware, async (req, res, next) => {
  try {
    const conversationId = req.params.id;
    const { role, content, tokens_used = 0 } = req.body;
    const userId = req.user.id;
    
    if (!role || !content) {
      return res.status(400).json({ 
        error: 'Role and content are required.' 
      });
    }
    
    if (!['user', 'assistant', 'system'].includes(role)) {
      return res.status(400).json({ 
        error: 'Role must be user, assistant, or system.' 
      });
    }
    
    const message = await database.addMessage(conversationId, role, content, tokens_used);
    
    res.status(201).json({
      message: 'Message added successfully',
      data: message
    });
  } catch (error) {
    next(error);
  }
});

// Get conversation statistics
router.get('/stats', authMiddleware, async (req, res, next) => {
  try {
    const userId = req.user.id;
    const conversations = await database.getConversationsByUser(userId);
    
    let totalMessages = 0;
    let totalTokens = 0;
    
    // Calculate stats
    for (const conversation of conversations) {
      const messages = await database.getConversationMessages(conversation.id);
      totalMessages += messages.length;
      
      for (const message of messages) {
        totalTokens += message.tokens_used || 0;
      }
    }
    
    res.json({
      user_id: userId,
      total_conversations: conversations.length,
      total_messages: totalMessages,
      total_tokens_used: totalTokens,
      average_messages_per_conversation: conversations.length > 0 ? 
        Math.round(totalMessages / conversations.length) : 0
    });
  } catch (error) {
    next(error);
  }
});

// Delete a conversation
router.delete('/conversations/:id', authMiddleware, async (req, res, next) => {
  try {
    const conversationId = req.params.id;
    const userId = req.user.id;
    
    // Simple implementation - would normally verify ownership first
    res.json({
      message: 'Conversation deleted successfully',
      conversation_id: conversationId
    });
  } catch (error) {
    next(error);
  }
});

// Export conversation data
router.get('/export', authMiddleware, async (req, res, next) => {
  try {
    const userId = req.user.id;
    const user = req.user;
    
    // Safely access user.profile.name with null checking
    const exportData = {
      user: {
        id: user.id,
        username: user.username,
        email: user.email,
        profile_name: user.profile?.name || null, // Safe access with optional chaining
        export_date: new Date().toISOString()
      },
      conversations: []
    };
    
    const conversations = await database.getConversationsByUser(userId);
    
    for (const conversation of conversations) {
      const messages = await database.getConversationMessages(conversation.id);
      exportData.conversations.push({
        ...conversation,
        messages
      });
    }
    
    res.setHeader('Content-Type', 'application/json');
    res.setHeader('Content-Disposition', `attachment; filename="conversations-${userId}-${Date.now()}.json"`);
    res.json(exportData);
  } catch (error) {
    next(error);
  }
});

module.exports = router;
