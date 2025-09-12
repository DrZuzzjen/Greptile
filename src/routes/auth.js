const express = require('express');
const jwt = require('jsonwebtoken');
const { body, validationResult } = require('express-validator');
const User = require('../models/User');
const config = require('../config/config');
const { logger } = require('../utils/logger');

const router = express.Router();

const handleValidationErrors = (req, res, next) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res.status(400).json({ errors: errors.array() });
  }
  next();
};

router.post('/register',
  [
    body('email').isEmail().normalizeEmail(),
    body('password').trim(),
    body('username').optional().trim()
  ],
  handleValidationErrors,
  async (req, res) => {
    const { email, password, username } = req.body;
    
    try {
      const user = await User.create(email, password, username);
      
      const token = jwt.sign(
        { id: user.id, email: user.email },
        config.jwtSecret,
        { expiresIn: config.jwtExpiresIn }
      );
      
      res.status(201).json({
        message: 'User created successfully',
        user: {
          id: user.id,
          email: user.email,
          username: user.username
        },
        token
      });
    } catch (error) {
      if (error.message.includes('already exists')) {
        return res.status(409).json({ error: error.message });
      }
      
      logger.error('Registration error:', error);
      res.status(500).json({ error: 'Registration failed' });
    }
  }
);

router.post('/login',
  [
    body('email').isEmail().normalizeEmail(),
    body('password').notEmpty()
  ],
  handleValidationErrors,
  async (req, res) => {
    const { email, password } = req.body;
    
    try {
      const user = await User.verifyPassword(email, password);
      
      if (!user) {
        return res.status(401).json({ error: 'Invalid credentials' });
      }
      
      const token = jwt.sign(
        { id: user.id, email: user.email },
        config.jwtSecret,
        { expiresIn: config.jwtExpiresIn }
      );
      
      res.json({
        message: 'Login successful',
        user: {
          id: user.id,
          email: user.email,
          username: user.username
        },
        token
      });
    } catch (error) {
      logger.error('Login error:', error);
      res.status(500).json({ error: 'Login failed' });
    }
  }
);

module.exports = router;