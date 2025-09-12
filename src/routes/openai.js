const express = require('express');
const { body, validationResult, query } = require('express-validator');
const authMiddleware = require('../middleware/auth');
const OpenAIService = require('../services/openai');
const Conversation = require('../models/Conversation');
const User = require('../models/User');
const { logger } = require('../utils/logger');

const router = express.Router();

const handleValidationErrors = (req, res, next) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res.status(400).json({ errors: errors.array() });
  }
  next();
};

router.get('/models', async (req, res) => {
  try {
    const models = await OpenAIService.getModels();
    res.json({ models });
  } catch (error) {
    logger.error('Error in /models endpoint:', error);
    res.status(500).json({ error: error.message });
  }
});

router.post('/chat',
  [
    body('messages').isArray().withMessage('Messages must be an array'),
    body('messages.*.role').isIn(['system', 'user', 'assistant']).withMessage('Invalid role'),
    body('messages.*.content').notEmpty().withMessage('Content cannot be empty'),
    body('model').optional().isString(),
    body('temperature').optional().isFloat({ min: 0, max: 2 }),
    body('max_tokens').optional().isInt({ min: 1 }),
    body('conversation_id').optional().isInt(),
    body('save_conversation').optional().isBoolean()
  ],
  handleValidationErrors,
  async (req, res) => {
    const { 
      messages, 
      model = 'gpt-3.5-turbo', 
      temperature,
      max_tokens,
      conversation_id,
      save_conversation = true,
      stream = false
    } = req.body;
    
    try {
      let conversationId = conversation_id;
      
      if (save_conversation && !conversationId) {
        const conversation = await Conversation.create(
          req.user.id,
          messages[0]?.content?.substring(0, 100) || 'New Chat',
          model
        );
        conversationId = conversation.id;
      }
      
      if (conversationId) {
        const conversation = await Conversation.findById(conversationId, req.user.id);
        if (!conversation) {
          return res.status(404).json({ error: 'Conversation not found' });
        }
      }
      
      const options = {};
      if (temperature !== undefined) options.temperature = temperature;
      if (max_tokens !== undefined) options.max_tokens = max_tokens;
      
      if (stream) {
        res.setHeader('Content-Type', 'text/event-stream');
        res.setHeader('Cache-Control', 'no-cache');
        res.setHeader('Connection', 'keep-alive');
        
        const stream = await OpenAIService.streamChatCompletion(messages, model, options);
        
        let fullContent = '';
        
        for await (const chunk of stream) {
          const content = chunk.choices[0]?.delta?.content || '';
          fullContent += content;
          
          res.write(`data: ${JSON.stringify(chunk)}\n\n`);
        }
        
        if (save_conversation && conversationId) {
          const messagesToSave = messages
            .filter(msg => msg.role === 'user')
            .map(msg => ({ role: msg.role, content: msg.content }));
          
          const estimatedTokens = Math.ceil(fullContent.length / 4);
          
          messagesToSave.push({ 
            role: 'assistant', 
            content: fullContent, 
            tokens_used: estimatedTokens 
          });
          
          await Conversation.addMessages(conversationId, messagesToSave);
        }
        
        res.write('data: [DONE]\n\n');
        res.end();
      } else {
        const completion = await OpenAIService.createChatCompletion(messages, model, options);
        
        if (save_conversation && conversationId) {
          const messagesToSave = messages
            .filter(msg => msg.role === 'user')
            .map(msg => ({ role: msg.role, content: msg.content }));
          
          const assistantMessage = completion.choices[0].message;
          messagesToSave.push({
            role: assistantMessage.role,
            content: assistantMessage.content,
            tokens_used: completion.usage?.total_tokens || 0
          });
          
          await Conversation.addMessages(conversationId, messagesToSave);
        }
        
        if (completion.usage) {
          await User.updateTokenUsage(
            req.user.id,
            completion.usage.prompt_tokens,
            completion.usage.completion_tokens
          );
        }
        
        res.json({
          ...completion,
          conversation_id: conversationId
        });
      }
    } catch (error) {
      logger.error('Error in /chat endpoint:', error);
      res.status(500).json({ error: error.message });
    }
  }
);

module.exports = router;