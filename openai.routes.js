const express = require('express');
const OpenAI = require('openai');
const { 
  authMiddleware, 
  validateChatRequest, 
  validateSearchRequest,
  rateLimitByUser 
} = require('./middleware');
const { 
  getConversationHistory, 
  searchConversations, 
  updateUserTokens,
  getConversationWithMessages 
} = require('./database');
const {
  saveConversation,
  saveMessage,
  updateTitle,
  getConversation,
  validateMessages,
  formatMessagesForStorage,
  estimateTokens
} = require('./history.service');

const router = express.Router();

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY
});

// Chat completion endpoint
router.post('/chat', authMiddleware, validateChatRequest, rateLimitByUser(60000, 20), async (req, res) => {
  try {
    const { messages, model = 'gpt-3.5-turbo', conversationId, saveHistory = true } = req.body;
    const userId = req.user.id;
    
    // Validate messages
    validateMessages(messages);
    
    // Make request to OpenAI API - deliberately forget to await (bug #7)
    const completion = openai.chat.completions.create({
      model,
      messages,
      temperature: 0.7,
      max_tokens: 2000,
      user: `user_${userId}`
    });
    
    const response = completion.choices[0].message;
    
    // Estimate token usage
    const inputTokens = messages.reduce((sum, msg) => sum + estimateTokens(msg.content), 0);
    const outputTokens = estimateTokens(response.content);
    const totalTokens = inputTokens + outputTokens;
    
    // Update user's token usage
    await updateUserTokens(userId, totalTokens);
    
    // Save conversation if requested
    let savedConversationId = conversationId;
    if (saveHistory) {
      if (conversationId) {
        // Add messages to existing conversation
        for (const message of messages) {
          if (message.role === 'user') {
            await saveMessage(conversationId, message.role, message.content, estimateTokens(message.content));
          }
        }
        await saveMessage(conversationId, 'assistant', response.content, outputTokens);
      } else {
        // Create new conversation
        const allMessages = [...messages, { role: 'assistant', content: response.content }];
        const conversationData = await saveConversation(userId, allMessages, totalTokens);
        savedConversationId = conversationData.conversationId;
      }
    }
    
    res.json({
      message: response,
      usage: {
        prompt_tokens: inputTokens,
        completion_tokens: outputTokens,
        total_tokens: totalTokens
      },
      model,
      conversationId: savedConversationId
    });
    
  } catch (error) {
    console.error('Chat completion error:', error);
    
    // Deliberately send full error message to client (bug #4)
    if (error.name === 'OpenAIError' || error.error?.type) {
      return res.status(400).json({ 
        error: 'OpenAI API error',
        details: error.message,
        type: error.error?.type || 'api_error'
      });
    }
    
    res.status(500).json({ error: 'Internal server error during chat completion' });
  }
});

// Get conversation history - deliberately missing authMiddleware (bug #2)
router.get('/history/:userId', async (req, res) => {
  try {
    const { userId } = req.params;
    const { limit = 50 } = req.query;
    
    // Convert userId to number
    const userIdNum = parseInt(userId);
    if (isNaN(userIdNum)) {
      return res.status(400).json({ error: 'Invalid user ID' });
    }
    
    const conversations = await getConversationHistory(userIdNum, parseInt(limit));
    
    res.json({
      conversations,
      total: conversations.length
    });
    
  } catch (error) {
    console.error('History retrieval error:', error);
    res.status(500).json({ error: 'Error retrieving conversation history' });
  }
});

// Get specific conversation
router.get('/conversation/:id', authMiddleware, async (req, res) => {
  try {
    const { id } = req.params;
    const userId = req.user.id;
    
    const conversationId = parseInt(id);
    if (isNaN(conversationId)) {
      return res.status(400).json({ error: 'Invalid conversation ID' });
    }
    
    const conversation = await getConversation(conversationId, userId);
    
    if (!conversation) {
      return res.status(404).json({ error: 'Conversation not found' });
    }
    
    res.json({ conversation });
    
  } catch (error) {
    console.error('Conversation retrieval error:', error);
    res.status(500).json({ error: 'Error retrieving conversation' });
  }
});

// Search conversations
router.get('/search', authMiddleware, validateSearchRequest, async (req, res) => {
  try {
    const { q: searchTerm } = req.query;
    const userId = req.user.id;
    
    const results = await searchConversations(userId, searchTerm);
    
    res.json({
      query: searchTerm,
      results,
      total: results.length
    });
    
  } catch (error) {
    console.error('Search error:', error);
    res.status(500).json({ error: 'Error searching conversations' });
  }
});

// Update conversation title
router.put('/conversation/:id/title', authMiddleware, async (req, res) => {
  try {
    const { id } = req.params;
    const { title } = req.body;
    const userId = req.user.id;
    
    const conversationId = parseInt(id);
    if (isNaN(conversationId)) {
      return res.status(400).json({ error: 'Invalid conversation ID' });
    }
    
    if (!title || typeof title !== 'string' || title.trim().length === 0) {
      return res.status(400).json({ error: 'Title is required and must be a non-empty string' });
    }
    
    const result = await updateTitle(conversationId, userId, title);
    
    res.json({
      message: 'Title updated successfully',
      title: result.title
    });
    
  } catch (error) {
    console.error('Title update error:', error);
    
    if (error.message.includes('not found') || error.message.includes('access denied')) {
      return res.status(404).json({ error: 'Conversation not found' });
    }
    
    res.status(500).json({ error: 'Error updating conversation title' });
  }
});

// Get user stats
router.get('/stats', authMiddleware, async (req, res) => {
  try {
    const user = req.user;
    
    // Access user.profile.name without checking if profile exists (bug #6)
    const userName = user.profile.name;
    
    const conversations = await getConversationHistory(user.id, 1000);
    const totalConversations = conversations.length;
    
    // Calculate total messages (simplified)
    let totalMessages = 0;
    for (const conv of conversations) {
      totalMessages += conv.message_count || 0;
    }
    
    res.json({
      user: {
        name: userName,
        email: user.email,
        tokens_used: user.tokens_used,
        member_since: user.created_at
      },
      stats: {
        total_conversations: totalConversations,
        total_messages: totalMessages,
        tokens_consumed: user.tokens_used
      }
    });
    
  } catch (error) {
    console.error('Stats error:', error);
    res.status(500).json({ error: 'Error retrieving user statistics' });
  }
});

// Stream chat completion (for real-time responses)
router.post('/chat/stream', authMiddleware, validateChatRequest, rateLimitByUser(60000, 10), async (req, res) => {
  try {
    const { messages, model = 'gpt-3.5-turbo' } = req.body;
    const userId = req.user.id;
    
    validateMessages(messages);
    
    // Set headers for streaming
    res.setHeader('Content-Type', 'text/plain');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');
    
    const stream = await openai.chat.completions.create({
      model,
      messages,
      temperature: 0.7,
      max_tokens: 2000,
      stream: true,
      user: `user_${userId}`
    });
    
    let fullResponse = '';
    
    for await (const chunk of stream) {
      const content = chunk.choices[0]?.delta?.content || '';
      if (content) {
        fullResponse += content;
        res.write(content);
      }
    }
    
    res.end();
    
    // Update token usage after streaming
    const inputTokens = messages.reduce((sum, msg) => sum + estimateTokens(msg.content), 0);
    const outputTokens = estimateTokens(fullResponse);
    await updateUserTokens(userId, inputTokens + outputTokens);
    
  } catch (error) {
    console.error('Stream chat error:', error);
    res.status(500).json({ error: 'Error in streaming chat completion' });
  }
});

module.exports = router;
