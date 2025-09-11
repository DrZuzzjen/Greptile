const express = require('express');
const axios = require('axios');
const database = require('./database');
const { 
  authMiddleware, 
  chatRateLimit, 
  validateChatRequest 
} = require('./middleware');

const router = express.Router();

// OpenAI API configuration
const OPENAI_API_URL = 'https://api.openai.com/v1';
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;

// Chat completions proxy endpoint
router.post('/chat/completions', authMiddleware, chatRateLimit, validateChatRequest, async (req, res, next) => {
  try {
    const { messages, model = 'gpt-3.5-turbo', temperature, max_tokens, stream = false } = req.body;
    const userId = req.user.id;
    const user = req.user;
    
    // Create conversation title from first user message
    const firstUserMessage = messages.find(msg => msg.role === 'user');
    const conversationTitle = firstUserMessage 
      ? firstUserMessage.content.substring(0, 50) + (firstUserMessage.content.length > 50 ? '...' : '')
      : 'New Conversation';
    
    // Create conversation in database
    const conversation = await database.createConversation(userId, conversationTitle);
    
    // Store user messages
    for (const message of messages) {
      if (message.role === 'user') {
        await database.addMessage(conversation.id, message.role, message.content);
      }
    }
    
    // Prepare OpenAI request
    const openaiRequest = {
      model,
      messages,
      temperature,
      max_tokens,
      stream
    };
    
    // Remove undefined values
    Object.keys(openaiRequest).forEach(key => 
      openaiRequest[key] === undefined && delete openaiRequest[key]
    );
    
    try {
      // Call OpenAI API - with proper await
      const openaiResponse = await axios.post(
        `${OPENAI_API_URL}/chat/completions`,
        openaiRequest,
        {
          headers: {
            'Authorization': `Bearer ${OPENAI_API_KEY}`,
            'Content-Type': 'application/json'
          }
        }
      );
      
      const responseData = openaiResponse.data;
      const assistantMessage = responseData.choices[0]?.message;
      const tokensUsed = responseData.usage?.total_tokens || 0;
      
      // Store assistant response
      if (assistantMessage) {
        await database.addMessage(
          conversation.id, 
          assistantMessage.role, 
          assistantMessage.content, 
          tokensUsed
        );
      }
      
      // Update user token usage
      await database.updateTokenUsage(userId, tokensUsed);
      
      // Return OpenAI response
      res.json({
        ...responseData,
        conversation_id: conversation.id,
        user_token_usage: user.token_usage + tokensUsed
      });
      
    } catch (openaiError) {
      console.error('OpenAI API Error:', openaiError);
      
      // Log error on server side but return generic message to client
      console.error('OpenAI API Error Details:', openaiError.response?.data);
      return res.status(500).json({
        error: 'OpenAI API Error',
        message: 'An unexpected error occurred with the OpenAI API. Please try again later.'
      });
    }
    
  } catch (error) {
    next(error);
  }
});

// Text completions proxy endpoint (legacy)
router.post('/completions', authMiddleware, chatRateLimit, async (req, res, next) => {
  try {
    const { prompt, model = 'gpt-3.5-turbo-instruct', max_tokens, temperature } = req.body;
    const userId = req.user.id;
    
    if (!prompt) {
      return res.status(400).json({ error: 'Prompt is required.' });
    }
    
    // Create conversation
    const conversation = await database.createConversation(userId, prompt.substring(0, 50) + '...');
    
    // Store prompt
    await database.addMessage(conversation.id, 'user', prompt);
    
    try {
      const openaiResponse = await axios.post(
        `${OPENAI_API_URL}/completions`,
        {
          model,
          prompt,
          max_tokens,
          temperature
        },
        {
          headers: {
            'Authorization': `Bearer ${OPENAI_API_KEY}`,
            'Content-Type': 'application/json'
          }
        }
      );
      
      const responseData = openaiResponse.data;
      const completion = responseData.choices[0]?.text;
      const tokensUsed = responseData.usage?.total_tokens || 0;
      
      // Store completion
      if (completion) {
        await database.addMessage(conversation.id, 'assistant', completion, tokensUsed);
      }
      
      // Update user token usage
      await database.updateTokenUsage(userId, tokensUsed);
      
      res.json({
        ...responseData,
        conversation_id: conversation.id
      });
      
    } catch (openaiError) {
      console.error('OpenAI API Error:', openaiError);
      
      // Log error on server side but return generic message to client
      console.error('OpenAI API Error Details:', openaiError.response?.data);
      return res.status(500).json({
        error: 'OpenAI API Error',
        message: 'An unexpected error occurred with the OpenAI API. Please try again later.'
      });
    }
    
  } catch (error) {
    next(error);
  }
});

// List available models
router.get('/models', authMiddleware, async (req, res, next) => {
  try {
    const openaiResponse = await axios.get(
      `${OPENAI_API_URL}/models`,
      {
        headers: {
          'Authorization': `Bearer ${OPENAI_API_KEY}`
        }
      }
    );
    
    res.json(openaiResponse.data);
    
  } catch (openaiError) {
    console.error('OpenAI API Error:', openaiError);
    
    return res.status(500).json({
      error: 'Failed to fetch models',
      message: openaiError.message
    });
  }
});

// Generate embeddings
router.post('/embeddings', authMiddleware, async (req, res, next) => {
  try {
    const { input, model = 'text-embedding-ada-002' } = req.body;
    const userId = req.user.id;
    
    if (!input) {
      return res.status(400).json({ error: 'Input is required.' });
    }
    
    try {
      const openaiResponse = await axios.post(
        `${OPENAI_API_URL}/embeddings`,
        {
          model,
          input
        },
        {
          headers: {
            'Authorization': `Bearer ${OPENAI_API_KEY}`,
            'Content-Type': 'application/json'
          }
        }
      );
      
      const responseData = openaiResponse.data;
      const tokensUsed = responseData.usage?.total_tokens || 0;
      
      // Update user token usage
      await database.updateTokenUsage(userId, tokensUsed);
      
      res.json(responseData);
      
    } catch (openaiError) {
      console.error('OpenAI API Error:', openaiError);
      
      // Log error on server side but return generic message to client
      console.error('OpenAI API Error Details:', openaiError.response?.data);
      return res.status(500).json({
        error: 'OpenAI API Error',
        message: 'An unexpected error occurred with the OpenAI API. Please try again later.'
      });
    }
    
  } catch (error) {
    next(error);
  }
});

// Image generation
router.post('/images/generations', authMiddleware, async (req, res, next) => {
  try {
    const { prompt, n = 1, size = '1024x1024', response_format = 'url' } = req.body;
    const userId = req.user.id;
    
    if (!prompt) {
      return res.status(400).json({ error: 'Prompt is required.' });
    }
    
    try {
      const openaiResponse = await axios.post(
        `${OPENAI_API_URL}/images/generations`,
        {
          prompt,
          n,
          size,
          response_format
        },
        {
          headers: {
            'Authorization': `Bearer ${OPENAI_API_KEY}`,
            'Content-Type': 'application/json'
          }
        }
      );
      
      const responseData = openaiResponse.data;
      
      // Create conversation for image generation
      const conversation = await database.createConversation(userId, `Image: ${prompt.substring(0, 40)}...`);
      await database.addMessage(conversation.id, 'user', `Generate image: ${prompt}`);
      await database.addMessage(conversation.id, 'assistant', `Generated ${n} image(s)`);
      
      res.json({
        ...responseData,
        conversation_id: conversation.id
      });
      
    } catch (openaiError) {
      console.error('OpenAI API Error:', openaiError);
      
      // Log error on server side but return generic message to client
      console.error('OpenAI API Error Details:', openaiError.response?.data);
      return res.status(500).json({
        error: 'OpenAI API Error',
        message: 'An unexpected error occurred with the OpenAI API. Please try again later.'
      });
    }
    
  } catch (error) {
    next(error);
  }
});

// Health check for OpenAI API
router.get('/health', authMiddleware, async (req, res, next) => {
  try {
    const startTime = Date.now();
    
    try {
      await axios.get(
        `${OPENAI_API_URL}/models`,
        {
          headers: {
            'Authorization': `Bearer ${OPENAI_API_KEY}`
          },
          timeout: 5000
        }
      );
      
      const responseTime = Date.now() - startTime;
      
      res.json({
        status: 'healthy',
        openai_api: 'accessible',
        response_time_ms: responseTime,
        timestamp: new Date().toISOString()
      });
      
    } catch (openaiError) {
      res.status(503).json({
        status: 'unhealthy',
        openai_api: 'inaccessible',
        error: openaiError.message,
        timestamp: new Date().toISOString()
      });
    }
    
  } catch (error) {
    next(error);
  }
});

module.exports = router;
