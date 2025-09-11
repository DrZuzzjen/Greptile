require('dotenv').config();
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const database = require('./database');
const { 
  errorHandler, 
  requestLogger, 
  securityHeaders, 
  generalRateLimit 
} = require('./middleware');

// Import route modules
const authRoutes = require('./auth.routes');
const openaiRoutes = require('./openai.routes');
const historyRoutes = require('./history.service');

const app = express();
const PORT = process.env.PORT || 3000;

// Global middleware
app.use(helmet());
app.use(cors({
  origin: process.env.CORS_ORIGIN || '*',
  credentials: true
}));
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));
app.use(requestLogger);
app.use(securityHeaders);
app.use(generalRateLimit);

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    version: '1.0.0',
    node_version: process.version,
    environment: process.env.NODE_ENV || 'development'
  });
});

// API routes
app.use('/api/auth', authRoutes);
app.use('/api/openai', openaiRoutes);
app.use('/api/history', historyRoutes);

// Root endpoint
app.get('/', (req, res) => {
  res.json({
    message: 'OpenAI Proxy Service',
    version: '1.0.0',
    endpoints: {
      auth: '/api/auth',
      openai: '/api/openai',
      history: '/api/history',
      health: '/health'
    },
    documentation: 'https://github.com/your-repo/openai-proxy-service'
  });
});

// API documentation endpoint
app.get('/api', (req, res) => {
  res.json({
    service: 'OpenAI Proxy Service',
    version: '1.0.0',
    endpoints: {
      authentication: {
        register: 'POST /api/auth/register',
        login: 'POST /api/auth/login',
        profile: 'GET /api/auth/me',
        update_profile: 'PUT /api/auth/profile',
        change_password: 'PUT /api/auth/password',
        usage: 'GET /api/auth/usage'
      },
      openai: {
        chat_completions: 'POST /api/openai/chat/completions',
        completions: 'POST /api/openai/completions',
        models: 'GET /api/openai/models',
        embeddings: 'POST /api/openai/embeddings',
        image_generation: 'POST /api/openai/images/generations',
        health: 'GET /api/openai/health'
      },
      history: {
        conversations: 'GET /api/history/conversations',
        conversation_detail: 'GET /api/history/conversations/:id',
        search: 'GET /api/history/search?q=term',
        user_history: 'GET /api/history/history/:userId',
        create_conversation: 'POST /api/history/conversations',
        add_message: 'POST /api/history/conversations/:id/messages',
        statistics: 'GET /api/history/stats',
        delete_conversation: 'DELETE /api/history/conversations/:id',
        export: 'GET /api/history/export'
      }
    },
    authentication: 'Bearer token required for most endpoints',
    rate_limits: {
      auth: '5 requests per 15 minutes',
      chat: '20 requests per minute',
      general: '100 requests per 15 minutes'
    }
  });
});

// 404 handler
app.use('*', (req, res) => {
  res.status(404).json({
    error: 'Not Found',
    message: `The endpoint ${req.method} ${req.originalUrl} does not exist.`,
    available_endpoints: '/api'
  });
});

// Global error handler
app.use(errorHandler);

// Graceful shutdown
process.on('SIGTERM', async () => {
  console.log('SIGTERM received, shutting down gracefully');
  try {
    await database.close();
    process.exit(0);
  } catch (error) {
    console.error('Error during shutdown:', error);
    process.exit(1);
  }
});

process.on('SIGINT', async () => {
  console.log('SIGINT received, shutting down gracefully');
  try {
    await database.close();
    process.exit(0);
  } catch (error) {
    console.error('Error during shutdown:', error);
    process.exit(1);
  }
});

// Initialize database and start server
async function startServer() {
  try {
    await database.connect();
    console.log('Database initialized successfully');
    
    app.listen(PORT, () => {
      console.log(`Server running on port ${PORT}`);
      console.log(`Environment: ${process.env.NODE_ENV || 'development'}`);
      console.log(`Health check: http://localhost:${PORT}/health`);
      console.log(`API documentation: http://localhost:${PORT}/api`);
    });
  } catch (error) {
    console.error('Failed to start server:', error);
    process.exit(1);
  }
}

// Start the server
if (require.main === module) {
  startServer();
}

module.exports = app;
