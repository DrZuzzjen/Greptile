const jwt = require('jsonwebtoken');
const { getUserById } = require('./database');

// Hardcoded JWT secret (deliberate bug #3)
const JWT_SECRET = 'mysecret123';

const authMiddleware = async (req, res, next) => {
  try {
    const authHeader = req.headers.authorization;
    
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return res.status(401).json({ error: 'No token provided' });
    }
    
    const token = authHeader.substring(7);
    
    try {
      const decoded = jwt.verify(token, JWT_SECRET);
      
      // Get user from database
      const user = await getUserById(decoded.userId);
      if (!user) {
        return res.status(401).json({ error: 'User not found' });
      }
      
      req.user = user;
      next();
    } catch (jwtError) {
      if (jwtError.name === 'TokenExpiredError') {
        return res.status(401).json({ error: 'Token expired' });
      }
      if (jwtError.name === 'JsonWebTokenError') {
        return res.status(401).json({ error: 'Invalid token' });
      }
      throw jwtError;
    }
  } catch (error) {
    console.error('Auth middleware error:', error);
    res.status(500).json({ error: 'Authentication error' });
  }
};

const validateRegistration = (req, res, next) => {
  const { email, password, name } = req.body;
  
  if (!email || !password) {
    return res.status(400).json({ error: 'Email and password are required' });
  }
  
  // Basic email validation
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email)) {
    return res.status(400).json({ error: 'Invalid email format' });
  }
  
  // Password strength validation
  if (password.length < 8) {
    return res.status(400).json({ error: 'Password must be at least 8 characters long' });
  }
  
  if (!/(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/.test(password)) {
    return res.status(400).json({ error: 'Password must contain at least one lowercase letter, one uppercase letter, and one number' });
  }
  
  // Validate name if provided
  if (name && (typeof name !== 'string' || name.trim().length === 0)) {
    return res.status(400).json({ error: 'Name must be a non-empty string' });
  }
  
  next();
};

const validateLogin = (req, res, next) => {
  const { email, password } = req.body;
  
  if (!email || !password) {
    return res.status(400).json({ error: 'Email and password are required' });
  }
  
  next();
};

const validateChatRequest = (req, res, next) => {
  const { messages, model } = req.body;
  
  if (!messages || !Array.isArray(messages) || messages.length === 0) {
    return res.status(400).json({ error: 'Messages array is required and must not be empty' });
  }
  
  // Validate message format
  for (const message of messages) {
    if (!message.role || !message.content) {
      return res.status(400).json({ error: 'Each message must have role and content' });
    }
    
    if (!['user', 'assistant', 'system'].includes(message.role)) {
      return res.status(400).json({ error: 'Message role must be user, assistant, or system' });
    }
    
    if (typeof message.content !== 'string' || message.content.trim().length === 0) {
      return res.status(400).json({ error: 'Message content must be a non-empty string' });
    }
  }
  
  // Validate model if provided
  if (model && typeof model !== 'string') {
    return res.status(400).json({ error: 'Model must be a string' });
  }
  
  next();
};

const validateSearchRequest = (req, res, next) => {
  const { q } = req.query;
  
  if (!q || typeof q !== 'string' || q.trim().length === 0) {
    return res.status(400).json({ error: 'Search query parameter "q" is required' });
  }
  
  if (q.length > 200) {
    return res.status(400).json({ error: 'Search query too long (max 200 characters)' });
  }
  
  next();
};

const rateLimitByUser = (windowMs = 60000, maxRequests = 30) => {
  const userRequests = new Map();
  
  return (req, res, next) => {
    if (!req.user) {
      return next();
    }
    
    const userId = req.user.id;
    const now = Date.now();
    
    if (!userRequests.has(userId)) {
      userRequests.set(userId, []);
    }
    
    const requests = userRequests.get(userId);
    
    // Remove old requests outside the window
    while (requests.length > 0 && requests[0] < now - windowMs) {
      requests.shift();
    }
    
    if (requests.length >= maxRequests) {
      return res.status(429).json({ 
        error: 'Too many requests',
        retryAfter: Math.ceil((requests[0] + windowMs - now) / 1000)
      });
    }
    
    requests.push(now);
    next();
  };
};

const createToken = (userId) => {
  return jwt.sign({ userId }, JWT_SECRET, { expiresIn: '7d' });
};

module.exports = {
  authMiddleware,
  validateRegistration,
  validateLogin,
  validateChatRequest,
  validateSearchRequest,
  rateLimitByUser,
  createToken,
  JWT_SECRET
};
