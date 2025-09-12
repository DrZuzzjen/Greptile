# OpenAI Proxy Microservice

Express.js microservice that acts as a secure proxy for OpenAI's API with user authentication, conversation history, and token usage tracking.

## Features

✅ **User Authentication**
- User registration and login with JWT tokens
- Secure password hashing with bcrypt
- JWT middleware for protected routes

✅ **OpenAI API Proxy**
- Get available models endpoint
- Chat completions with conversation storage
- Streaming chat support
- All conversations stored under user ID

✅ **Conversation Management**
- SQLite database for conversation history
- Get conversations list with pagination
- Get individual conversation with messages
- Message count tracking per conversation

✅ **Token Usage Tracking**
- Track prompt and completion tokens per user
- Daily token usage aggregation
- Token usage history with date ranges
- Accurate token counting for both regular and streaming responses

## API Endpoints

### Authentication
- `POST /api/auth/register` - User registration
- `POST /api/auth/login` - User login

### OpenAI Proxy (Requires Authentication)
- `GET /api/openai/models` - Get available OpenAI models
- `POST /api/openai/chat` - Chat completions with conversation storage

### History (Requires Authentication)
- `GET /api/history/conversations` - Get user's conversations (paginated)
- `GET /api/history/conversations/:id` - Get specific conversation with messages
- `GET /api/history/token-usage` - Get user's token usage statistics

### Health
- `GET /health` - Health check endpoint

## Security Features

- Helmet.js for security headers
- CORS configuration
- Rate limiting (100 requests per 15 minutes)
- Input validation with express-validator
- JWT authentication middleware
- Secure password hashing
- Database transactions for data consistency

## Database Schema

### Users Table
- User authentication and profile information
- Secure password storage

### Conversations Table
- Conversation metadata (title, model, timestamps)
- User association for privacy

### Messages Table
- Individual messages within conversations
- Role-based message storage (user/assistant)
- Token usage tracking per message

### Token Usage Table
- Daily token usage aggregation per user
- Prompt, completion, and total token tracking

## Installation

1. Install dependencies:
```bash
npm install
```

2. Set up environment variables in `.env`:
```
OPENAI_API_KEY=your_openai_api_key
JWT_SECRET=your_jwt_secret
PORT=3000
DB_PATH=./database.sqlite
RATE_LIMIT=100
JWT_EXPIRES_IN=24h
```

3. Start the server:
```bash
npm start
```

For development:
```bash
npm run dev
```

## Usage Examples

### Register a user:
```bash
curl -X POST http://localhost:3000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123", "username": "testuser"}'
```

### Login:
```bash
curl -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}'
```

### Chat with OpenAI:
```bash
curl -X POST http://localhost:3000/api/openai/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{"messages": [{"role": "user", "content": "Hello!"}], "model": "gpt-3.5-turbo"}'
```

### Get conversations:
```bash
curl -X GET http://localhost:3000/api/history/conversations \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Get token usage:
```bash
curl -X GET http://localhost:3000/api/history/token-usage \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## Project Structure

```
src/
├── app.js              # Main application file
├── config/
│   └── config.js       # Configuration settings
├── middleware/
│   └── auth.js         # JWT authentication middleware
├── models/
│   ├── database.js     # Database initialization and schema
│   ├── User.js         # User model with authentication methods
│   └── Conversation.js # Conversation and message models
├── routes/
│   ├── auth.js         # Authentication routes
│   ├── openai.js       # OpenAI proxy routes
│   └── history.js      # Conversation history routes
├── services/
│   └── openai.js       # OpenAI API service layer
└── utils/
    └── logger.js       # Logging utilities
```

## Verification Status

✅ All phases completed and verified with Kluster MCP:
- Phase 1: Project setup and dependencies ✅
- Phase 2: Database schema and authentication ✅ 
- Phase 3: OpenAI proxy endpoints ✅
- Phase 4: Conversation history storage ✅
- Phase 5: Token usage tracking ✅
- Phase 6: Final testing and verification ✅

## Performance & Security Features

- Secure JWT-based authentication system
- SQLite database with optimized queries
- Rate limiting and CORS protection
- Input validation with express-validator
- Structured logging with Winston
- Streaming chat completions support
- Token usage tracking and analytics
- Pagination for conversation history