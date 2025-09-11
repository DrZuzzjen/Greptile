const { 
  createConversation, 
  addMessage, 
  updateConversationTitle,
  getConversationWithMessages 
} = require('./database');

const generateConversationTitle = (messages) => {
  if (!messages || messages.length === 0) {
    return 'New Conversation';
  }
  
  // Get first user message
  const firstUserMessage = messages.find(msg => msg.role === 'user');
  if (!firstUserMessage) {
    return 'New Conversation';
  }
  
  // Extract title from first message
  let title = firstUserMessage.content.slice(0, 50);
  if (firstUserMessage.content.length > 50) {
    title += '...';
  }
  
  return title;
};

const saveConversation = async (userId, messages, tokensUsed = 0) => {
  try {
    // Generate title from first message
    const title = generateConversationTitle(messages);
    
    // Create conversation
    const conversation = await createConversation(userId, title);
    
    // Save all messages
    for (const message of messages) {
      await addMessage(
        conversation.id,
        message.role,
        message.content,
        message.tokens || 0
      );
    }
    
    return {
      conversationId: conversation.id,
      title,
      messageCount: messages.length
    };
    
  } catch (error) {
    console.error('Error saving conversation:', error);
    throw new Error('Failed to save conversation');
  }
};

const saveMessage = async (conversationId, role, content, tokens = 0) => {
  try {
    const message = await addMessage(conversationId, role, content, tokens);
    return message;
  } catch (error) {
    console.error('Error saving message:', error);
    throw new Error('Failed to save message');
  }
};

const updateTitle = async (conversationId, userId, newTitle) => {
  try {
    if (!newTitle || typeof newTitle !== 'string' || newTitle.trim().length === 0) {
      throw new Error('Invalid title provided');
    }
    
    const result = await updateConversationTitle(conversationId, userId, newTitle.trim());
    
    if (!result.updated) {
      throw new Error('Conversation not found or access denied');
    }
    
    return { success: true, title: newTitle.trim() };
    
  } catch (error) {
    console.error('Error updating conversation title:', error);
    throw error;
  }
};

const getConversation = async (conversationId, userId) => {
  try {
    const conversation = await getConversationWithMessages(conversationId, userId);
    
    if (!conversation) {
      return null;
    }
    
    return {
      id: conversation.id,
      title: conversation.title,
      messages: conversation.messages.map(msg => ({
        id: msg.id,
        role: msg.role,
        content: msg.content,
        tokens: msg.tokens,
        created_at: msg.created_at
      })),
      created_at: conversation.created_at,
      updated_at: conversation.updated_at
    };
    
  } catch (error) {
    console.error('Error getting conversation:', error);
    throw new Error('Failed to retrieve conversation');
  }
};

const estimateTokens = (text) => {
  // Simple token estimation: roughly 1 token per 4 characters
  // This is a very rough approximation - OpenAI's actual tokenization is more complex
  return Math.ceil(text.length / 4);
};

const validateMessages = (messages) => {
  if (!Array.isArray(messages)) {
    throw new Error('Messages must be an array');
  }
  
  if (messages.length === 0) {
    throw new Error('Messages array cannot be empty');
  }
  
  for (let i = 0; i < messages.length; i++) {
    const message = messages[i];
    
    if (!message.role || !message.content) {
      throw new Error(`Message ${i} is missing role or content`);
    }
    
    if (!['user', 'assistant', 'system'].includes(message.role)) {
      throw new Error(`Message ${i} has invalid role: ${message.role}`);
    }
    
    if (typeof message.content !== 'string') {
      throw new Error(`Message ${i} content must be a string`);
    }
    
    if (message.content.length > 32000) {
      throw new Error(`Message ${i} content too long (max 32000 characters)`);
    }
  }
  
  return true;
};

const formatMessagesForStorage = (messages, response = null) => {
  const formattedMessages = messages.map(msg => ({
    role: msg.role,
    content: msg.content,
    tokens: estimateTokens(msg.content)
  }));
  
  // Add response if provided
  if (response) {
    formattedMessages.push({
      role: 'assistant',
      content: response.content || response,
      tokens: estimateTokens(response.content || response)
    });
  }
  
  return formattedMessages;
};

module.exports = {
  saveConversation,
  saveMessage,
  updateTitle,
  getConversation,
  generateConversationTitle,
  estimateTokens,
  validateMessages,
  formatMessagesForStorage
};
