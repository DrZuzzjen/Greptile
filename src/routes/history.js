const express = require('express');
const { query, param, validationResult } = require('express-validator');
const authMiddleware = require('../middleware/auth');
const Conversation = require('../models/Conversation');
const User = require('../models/User');
const { logger } = require('../utils/logger');

const router = express.Router();

router.use(authMiddleware);

const handleValidationErrors = (req, res, next) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res.status(400).json({ errors: errors.array() });
  }
  next();
};

router.get('/conversations',
  [
    query('limit').optional().isInt({ min: 1, max: 100 }),
    query('offset').optional().isInt({ min: 0 })
  ],
  handleValidationErrors,
  async (req, res) => {
    const limit = parseInt(req.query.limit) || 50;
    const offset = parseInt(req.query.offset) || 0;
    
    try {
      const conversations = await Conversation.findByUserId(
        req.user.id,
        limit,
        offset
      );
      
      res.json({
        conversations,
        pagination: {
          limit,
          offset,
          total: conversations.length
        }
      });
    } catch (error) {
      logger.error('Error fetching conversations:', error);
      res.status(500).json({ error: 'Failed to fetch conversations' });
    }
  }
);

router.get('/conversations/:id',
  [
    param('id').isInt()
  ],
  handleValidationErrors,
  async (req, res) => {
    const conversationId = req.params.id;
    
    try {
      const conversation = await Conversation.findById(conversationId, req.user.id);
      
      if (!conversation) {
        return res.status(404).json({ error: 'Conversation not found' });
      }
      
      const messages = await Conversation.getMessages(conversationId, req.user.id);
      
      res.json({
        conversation,
        messages
      });
    } catch (error) {
      logger.error('Error fetching conversation:', error);
      res.status(500).json({ error: 'Failed to fetch conversation' });
    }
  }
);

router.get('/token-usage',
  [
    query('start_date').optional().isISO8601(),
    query('end_date').optional().isISO8601()
  ],
  handleValidationErrors,
  async (req, res) => {
    const { start_date, end_date } = req.query;
    
    try {
      const usage = await User.getTokenUsage(
        req.user.id,
        start_date,
        end_date
      );
      
      const totals = usage.reduce((acc, day) => ({
        prompt_tokens: acc.prompt_tokens + day.prompt_tokens,
        completion_tokens: acc.completion_tokens + day.completion_tokens,
        total_tokens: acc.total_tokens + day.total_tokens
      }), { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 });
      
      res.json({
        usage,
        totals,
        period: {
          start: start_date || usage[usage.length - 1]?.date,
          end: end_date || usage[0]?.date
        }
      });
    } catch (error) {
      logger.error('Error fetching token usage:', error);
      res.status(500).json({ error: 'Failed to fetch token usage' });
    }
  }
);

module.exports = router;