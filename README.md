# OpenAI Proxy Service

A comprehensive Express.js microservice that acts as a proxy for OpenAI's API with user authentication, conversation history, and rate limiting.

## Features

- 🔐 JWT-based user authentication
- 🚀 OpenAI API proxy endpoints
- 📊 SQLite database for conversation storage
- 🔍 Search functionality for past conversations
- ⚡ Rate limiting and security middleware
- 📈 Token usage tracking per user
- 🛡️ Security headers and input validation

## Project Structure

```
├── app.js              # Express application setup
├── auth.routes.js      # Authentication endpoints
├── openai.routes.js    # OpenAI proxy endpoints
├── database.js         # SQLite database setup and queries
├── middleware.js       # Authentication and validation middleware
├── history.service.js  # Conversation storage and retrieval
├── package.json        # Dependencies and scripts
└── README.md          # This file
```

## Installation

1. Clone the repository
2. Install dependencies:
```bash
npm install
```

3. Set up environment variables by creating a `.env` file:
```env
OPENAI_API_KEY=your_openai_api_key_here
JWT_SECRET=your_jwt_secret_here
PORT=3000
NODE_ENV=development
```

4. Start the server:
```bash
npm start
```

For development with auto-reload:
```bash
npm run dev
```

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register a new user
- `POST /api/auth/login` - Login user
- `GET /api/auth/me` - Get current user profile
- `PUT /api/auth/profile` - Update user profile
- `PUT /api/auth/password` - Change password
- `GET /api/auth/usage` - Get token usage statistics

### OpenAI Proxy
- `POST /api/openai/chat/completions` - Chat completions
- `POST /api/openai/completions` - Text completions (legacy)
- `GET /api/openai/models` - List available models
- `POST /api/openai/embeddings` - Generate embeddings
- `POST /api/openai/images/generations` - Generate images
- `GET /api/openai/health` - OpenAI API health check

### History & Conversations
- `GET /api/history/conversations` - Get user conversations
- `GET /api/history/conversations/:id` - Get conversation messages
- `GET /api/history/search?q=term` - Search conversations
- `GET /api/history/history/:userId` - Get user history
- `POST /api/history/conversations` - Create new conversation
- `POST /api/history/conversations/:id/messages` - Add message
- `GET /api/history/stats` - Get conversation statistics
- `DELETE /api/history/conversations/:id` - Delete conversation
- `GET /api/history/export` - Export conversation data

### System
- `GET /health` - Service health check
- `GET /api` - API documentation

## Usage Examples

### Register a new user
```bash
curl -X POST http://localhost:3000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "password123"
  }'
```

### Login
```bash
curl -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123"
  }'
```

### Chat with OpenAI
```bash
curl -X POST http://localhost:3000/api/openai/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "messages": [
      {"role": "user", "content": "Hello, how are you?"}
    ],
    "model": "gpt-3.5-turbo"
  }'
```

### Search conversations
```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  "http://localhost:3000/api/history/search?q=hello"
```

## Rate Limits

- Authentication endpoints: 5 requests per 15 minutes
- Chat endpoints: 20 requests per minute
- General endpoints: 100 requests per 15 minutes

## Security Features

- JWT authentication with configurable secret
- Rate limiting on all endpoints
- Input validation and sanitization
- Security headers with Helmet.js
- CORS configuration
- SQL injection protection (prepared statements)
- Password hashing with bcrypt

## Database Schema

The service uses SQLite with the following tables:
- `users` - User accounts and token usage
- `profiles` - User profile information
- `conversations` - Conversation metadata
- `messages` - Individual messages in conversations

## Error Handling

The service includes comprehensive error handling with:
- Structured error responses
- Request logging
- Graceful shutdown handling
- OpenAI API error forwarding

## Development

To run in development mode with automatic restarts:
```bash
npm run dev
```

The service will start on port 3000 by default. Visit:
- `http://localhost:3000/health` for health check
- `http://localhost:3000/api` for API documentation

## License

MIT License
