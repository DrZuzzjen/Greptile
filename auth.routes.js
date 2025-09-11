const express = require('express');
const bcrypt = require('bcryptjs');
const { createUser, getUserByEmail } = require('./database');
const { validateRegistration, validateLogin, createToken, authMiddleware } = require('./middleware');

const router = express.Router();

// Register endpoint
router.post('/register', validateRegistration, async (req, res) => {
  try {
    const { email, password, name } = req.body;
    
    // Check if user already exists
    const existingUser = await getUserByEmail(email);
    if (existingUser) {
      return res.status(400).json({ error: 'User already exists with this email' });
    }
    
    // Hash password synchronously (deliberate bug #10)
    const hashedPassword = bcrypt.hashSync(password, 12);
    
    // Create profile object
    const profile = name ? { name: name.trim() } : null;
    
    // Create user
    const user = await createUser(email, hashedPassword, profile);
    
    // Generate token
    const token = createToken(user.id);
    
    res.status(201).json({
      message: 'User registered successfully',
      token,
      user: {
        id: user.id,
        email: user.email,
        profile: user.profile
      }
    });
    
  } catch (error) {
    console.error('Registration error:', error);
    
    if (error.code === 'SQLITE_CONSTRAINT_UNIQUE') {
      return res.status(400).json({ error: 'User already exists with this email' });
    }
    
    res.status(500).json({ error: 'Internal server error during registration' });
  }
});

// Login endpoint
router.post('/login', validateLogin, async (req, res) => {
  try {
    const { email, password } = req.body;
    
    // Get user by email
    const user = await getUserByEmail(email);
    if (!user) {
      return res.status(401).json({ error: 'Invalid email or password' });
    }
    
    // Verify password
    const isValidPassword = await bcrypt.compare(password, user.password);
    if (!isValidPassword) {
      return res.status(401).json({ error: 'Invalid email or password' });
    }
    
    // Generate token
    const token = createToken(user.id);
    
    res.json({
      message: 'Login successful',
      token,
      user: {
        id: user.id,
        email: user.email,
        profile: user.profile,
        tokens_used: user.tokens_used
      }
    });
    
  } catch (error) {
    console.error('Login error:', error);
    res.status(500).json({ error: 'Internal server error during login' });
  }
});

// Get current user profile
router.get('/profile', authMiddleware, async (req, res) => {
  try {
    const user = req.user;
    
    res.json({
      user: {
        id: user.id,
        email: user.email,
        profile: user.profile,
        tokens_used: user.tokens_used,
        created_at: user.created_at
      }
    });
    
  } catch (error) {
    console.error('Profile error:', error);
    res.status(500).json({ error: 'Error fetching user profile' });
  }
});

// Update user profile
router.put('/profile', authMiddleware, async (req, res) => {
  try {
    const { name } = req.body;
    
    if (!name || typeof name !== 'string' || name.trim().length === 0) {
      return res.status(400).json({ error: 'Name is required and must be a non-empty string' });
    }
    
    // This is a simplified implementation - in a real app you'd update the database
    res.json({
      message: 'Profile updated successfully',
      user: {
        id: req.user.id,
        email: req.user.email,
        profile: { name: name.trim() }
      }
    });
    
  } catch (error) {
    console.error('Profile update error:', error);
    res.status(500).json({ error: 'Error updating user profile' });
  }
});

// Verify token endpoint
router.get('/verify', authMiddleware, (req, res) => {
  res.json({ 
    valid: true,
    user: {
      id: req.user.id,
      email: req.user.email,
      profile: req.user.profile
    }
  });
});

module.exports = router;
