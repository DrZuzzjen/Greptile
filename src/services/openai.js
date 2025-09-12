const OpenAI = require('openai');
const config = require('../config/config');
const { logger, sanitizeError } = require('../utils/logger');

const openai = new OpenAI({
  apiKey: config.openaiApiKey
});

class OpenAIService {
  static async getModels() {
    try {
      const response = await openai.models.list();
      return response.data;
    } catch (error) {
      logger.error('Error fetching models:', sanitizeError(error));
      throw new Error('Failed to fetch models');
    }
  }

  static async createChatCompletion(messages, model = 'gpt-3.5-turbo', options = {}) {
    try {
      const completion = openai.chat.completions.create({
        model,
        messages,
        ...options
      });
      
      return {
        id: completion.id,
        model: completion.model,
        choices: completion.choices,
        usage: completion.usage
      };
    } catch (error) {
      logger.error('Error creating chat completion:', sanitizeError(error));
      
      if (error.status === 429) {
        throw new Error('Rate limit exceeded. Please try again later.');
      }
      if (error.status === 401) {
        throw new Error('Authentication failed');
      }
      if (error.status === 400) {
        throw new Error('Invalid request parameters');
      }
      
      throw new Error('Failed to create chat completion');
    }
  }

  static async streamChatCompletion(messages, model = 'gpt-3.5-turbo', options = {}) {
    try {
      const stream = openai.chat.completions.create({
        model,
        messages,
        stream: true,
        ...options
      });
      
      return stream;
    } catch (error) {
      logger.error('Error creating stream:', sanitizeError(error));
      
      if (error.status === 429) {
        throw new Error('Rate limit exceeded. Please try again later.');
      }
      if (error.status === 401) {
        throw new Error('Authentication failed');
      }
      
      throw new Error('Failed to create chat stream');
    }
  }
}

module.exports = OpenAIService;