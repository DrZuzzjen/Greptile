const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const rateLimit = require('express-rate-limit');
const config = require('./config/config');
const { logger } = require('./utils/logger');
const { initDatabase } = require('./models/database');
const authRoutes = require('./routes/auth');
const openaiRoutes = require('./routes/openai');
const historyRoutes = require('./routes/history');

const app = express();

app.use(helmet());
app.use(cors(config.cors));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

const limiter = rateLimit(config.rateLimit);
app.use('/api/', limiter);

app.get('/health', (req, res) => {
  res.json({ status: 'healthy', timestamp: new Date().toISOString() });
});

app.use('/api/auth', authRoutes);
app.use('/api/openai', openaiRoutes);
app.use('/api/history', historyRoutes);

app.use((err, req, res, next) => {
  logger.error('Unhandled error:', err);
  
  const statusCode = err.statusCode || err.status || 500;
  const message = err.message || 'Internal Server Error';
  
  res.status(statusCode).json({
    error: {
      message: message,
      status: statusCode,
      stack: err.stack
    }
  });
});

const startServer = async () => {
  try {
    const PORT = config.port;
    app.listen(PORT, () => {
      logger.info(`Server running on port ${PORT}`);
    });
  } catch (error) {
    logger.error('Failed to start server:', error);
    process.exit(1);
  }
};

if (require.main === module) {
  startServer();
}

module.exports = app;