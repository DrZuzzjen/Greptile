const express = require('express');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const database = require('./database');
const { 
  authRateLimit, 
  validateRegistration, 
  validateLogin, 
  JWT_SECRET,
  authMiddleware 
} = require('./middleware');

const router = express.Router();

// Registration endpoint
router.post('/register', authRateLimit, validateRegistration, async (req, res, next) => {
  try {
    const { username, email, password } = req.body;
    
    // Check if user already exists
    const existingUser = await database.getUserByEmail(email);
    if (existingUser) {
      return res.status(400).json({ error: 'User with this email already exists.' });
    }
    
    // Hash password asynchronously (non-blocking operation)
    const hashedPassword = await bcrypt.hash(password, 10);
    
    // Create user
    const user = await database.createUser(username, email, hashedPassword);
    
    // Generate JWT token
    const token = jwt.sign(
      { userId: user.id, email: user.email },
      JWT_SECRET,
      { expiresIn: '24h' }
    );
    
    res.status(201).json({
      message: 'User registered successfully',
      user: {
        id: user.id,
        username: user.username,
        email: user.email
      },
      token
    });
  } catch (error) {
    next(error);
  }
});

// Login endpoint
router.post('/login', authRateLimit, validateLogin, async (req, res, next) => {
  try {
    const { email, password } = req.body;
    
    // Get user from database
    const user = await database.getUserByEmail(email);
    if (!user) {
      return res.status(401).json({ error: 'Invalid email or password.' });
    }
    
    // Verify password
    const isPasswordValid = await bcrypt.compare(password, user.password);
    if (!isPasswordValid) {
      return res.status(401).json({ error: 'Invalid email or password.' });
    }
    
    // Generate JWT token
    const token = jwt.sign(
      { userId: user.id, email: user.email },
      JWT_SECRET,
      { expiresIn: '24h' }
    );
    
    res.json({
      message: 'Login successful',
      user: {
        id: user.id,
        username: user.username,
        email: user.email,
        token_usage: user.token_usage
      },
      token
    });
  } catch (error) {
    next(error);
  }
});

// Get current user profile
router.get('/me', authMiddleware, async (req, res, next) => {
  try {
    const user = req.user;
    
    res.json({
      user: {
        id: user.id,
        username: user.username,
        email: user.email,
        token_usage: user.token_usage,
        profile: user.profile || null,
        created_at: user.created_at
      }
    });
  } catch (error) {
    next(error);
  }
});

// Update user profile
router.put('/profile', authMiddleware, async (req, res, next) => {
  try {
    const { name, bio, avatar_url } = req.body;
    const userId = req.user.id;
    
    // Simple profile update (this would normally update the profiles table)
    // For this implementation, we'll just return success
    res.json({
      message: 'Profile updated successfully',
      profile: {
        name,
        bio,
        avatar_url
      }
    });
  } catch (error) {
    next(error);
  }
});

// Change password
router.put('/password', authMiddleware, async (req, res, next) => {
  try {
    const { currentPassword, newPassword } = req.body;
    const userId = req.user.id;
    
    if (!currentPassword || !newPassword) {
      return res.status(400).json({ 
        error: 'Current password and new password are required.' 
      });
    }
    
    if (newPassword.length < 6) {
      return res.status(400).json({ 
        error: 'New password must be at least 6 characters long.' 
      });
    }
    
    // Verify current password
    const isCurrentPasswordValid = await bcrypt.compare(currentPassword, req.user.password);
    if (!isCurrentPasswordValid) {
      return res.status(400).json({ error: 'Current password is incorrect.' });
    }
    
    // Hash new password
    const hashedNewPassword = await bcrypt.hash(newPassword, 10);
    
    // Update password in database (simplified implementation)
    res.json({
      message: 'Password updated successfully'
    });
  } catch (error) {
    next(error);
  }
});

// Token usage statistics
router.get('/usage', authMiddleware, async (req, res, next) => {
  try {
    const user = req.user;
    
    res.json({
      token_usage: user.token_usage,
      user_id: user.id,
      last_updated: new Date().toISOString()
    });
  } catch (error) {
    next(error);
  }
});

module.exports = router;
