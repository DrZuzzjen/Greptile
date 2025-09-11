const jwt = require('jsonwebtoken');
const rateLimit = require('express-rate-limit');
const database = require('./database');

// JWT Secret - load from environment variables
const JWT_SECRET = process.env.JWT_SECRET || 'mysecret123';

// Authentication middleware
const authMiddleware = async (req, res, next) => {
  try {
    const token = req.header('Authorization')?.replace('Bearer ', '');
    
    if (!token) {
      return res.status(401).json({ error: 'Access denied. No token provided.' });
    }

    const decoded = jwt.verify(token, JWT_SECRET);
    const user = await database.getUserById(decoded.userId);
    
    if (!user) {
      return res.status(401).json({ error: 'Invalid token. User not found.' });
    }

    req.user = user;
    next();
  } catch (error) {
    console.error('Auth middleware error:', error);
    return res.status(401).json({ error: 'Invalid token.' });
  }
};

// Rate limiting middleware
const createRateLimit = (windowMs, max, message) => {
  return rateLimit({
    windowMs,
    max,
    message: { error: message },
    standardHeaders: true,
    legacyHeaders: false,
  });
};

// Different rate limits for different endpoints
const authRateLimit = createRateLimit(
  15 * 60 * 1000, // 15 minutes
  5, // 5 attempts
  'Too many authentication attempts, please try again later.'
);

const chatRateLimit = createRateLimit(
  60 * 1000, // 1 minute
  20, // 20 requests
  'Too many chat requests, please try again later.'
);

const generalRateLimit = createRateLimit(
  15 * 60 * 1000, // 15 minutes
  100, // 100 requests
  'Too many requests, please try again later.'
);

// Validation middleware
const validateRegistration = (req, res, next) => {
  const { username, email, password } = req.body;
  
  if (!username || !email || !password) {
    return res.status(400).json({ 
      error: 'Username, email, and password are required.' 
    });
  }
  
  if (username.length < 3) {
    return res.status(400).json({ 
      error: 'Username must be at least 3 characters long.' 
    });
  }
  
  if (password.length < 6) {
    return res.status(400).json({ 
      error: 'Password must be at least 6 characters long.' 
    });
  }
  
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email)) {
    return res.status(400).json({ 
      error: 'Please provide a valid email address.' 
    });
  }
  
  next();
};

const validateLogin = (req, res, next) => {
  const { email, password } = req.body;
  
  if (!email || !password) {
    return res.status(400).json({ 
      error: 'Email and password are required.' 
    });
  }
  
  next();
};

const validateChatRequest = (req, res, next) => {
  const { messages, model } = req.body;
  
  if (!messages || !Array.isArray(messages) || messages.length === 0) {
    return res.status(400).json({ 
      error: 'Messages array is required and must not be empty.' 
    });
  }
  
  for (const message of messages) {
    if (!message.role || !message.content) {
      return res.status(400).json({ 
        error: 'Each message must have role and content properties.' 
      });
    }
    
    if (!['system', 'user', 'assistant'].includes(message.role)) {
      return res.status(400).json({ 
        error: 'Message role must be system, user, or assistant.' 
      });
    }
  }
  
  if (model && typeof model !== 'string') {
    return res.status(400).json({ 
      error: 'Model must be a string.' 
    });
  }
  
  next();
};

// Error handling middleware
const errorHandler = (err, req, res, next) => {
  console.error('Error:', err);
  
  if (err.name === 'JsonWebTokenError') {
    return res.status(401).json({ error: 'Invalid token.' });
  }
  
  if (err.name === 'TokenExpiredError') {
    return res.status(401).json({ error: 'Token expired.' });
  }
  
  if (err.code === 'SQLITE_CONSTRAINT_UNIQUE') {
    return res.status(400).json({ error: 'User already exists.' });
  }
  
  // Default error response
  res.status(500).json({ 
    error: 'Internal server error.',
    details: process.env.NODE_ENV === 'development' ? err.message : undefined
  });
};

// Request logging middleware
const requestLogger = (req, res, next) => {
  const timestamp = new Date().toISOString();
  const method = req.method;
  const url = req.url;
  const userAgent = req.get('User-Agent');
  
  console.log(`[${timestamp}] ${method} ${url} - ${userAgent}`);
  
  next();
};

// Security headers middleware
const securityHeaders = (req, res, next) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('X-XSS-Protection', '1; mode=block');
  res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
  
  next();
};

module.exports = {
  authMiddleware,
  authRateLimit,
  chatRateLimit,
  generalRateLimit,
  validateRegistration,
  validateLogin,
  validateChatRequest,
  errorHandler,
  requestLogger,
  securityHeaders,
  JWT_SECRET
};
