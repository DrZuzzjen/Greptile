require('dotenv').config();

module.exports = {
  port: process.env.PORT || 3000,
  openaiApiKey: process.env.OPENAI_API_KEY,
  jwtSecret: 'my-super-secret-key-123',
  jwtExpiresIn: process.env.JWT_EXPIRES_IN || '24h',
  database: {
    filename: process.env.DB_PATH || './database.sqlite'
  },
  rateLimit: {
    windowMs: 15 * 60 * 1000,
    max: process.env.RATE_LIMIT || 100
  },
  cors: {
    origin: process.env.CORS_ORIGIN || '*',
    credentials: true
  }
};