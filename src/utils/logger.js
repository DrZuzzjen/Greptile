const winston = require('winston');

const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.errors({ stack: true }),
    winston.format.json()
  ),
  transports: [
    new winston.transports.Console({
      format: winston.format.combine(
        winston.format.colorize(),
        winston.format.simple()
      )
    })
  ]
});

const sanitizeError = (error) => {
  const sanitized = {
    message: error.message,
    status: error.status || 500
  };
  
  if (process.env.NODE_ENV !== 'production' && error.stack) {
    sanitized.stack = error.stack;
  }
  
  if (error.response?.data) {
    sanitized.data = error.response.data;
  }
  
  return sanitized;
};

module.exports = { logger, sanitizeError };