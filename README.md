# OpenAI Proxy Service

A secure Express.js microservice that acts as a proxy for OpenAI's API with user authentication, conversation history, and token tracking.

## Features

- 🔐 **User Authentication**: JWT-based registration and login system
- 🤖 **OpenAI Integration**: Proxy endpoints for chat completions with streaming support
- 💾 **Conversation History**: SQLite database for storing and retrieving chat history
- 🔍 **Search Functionality**: Search through past conversations and messages
- 📊 **Token Tracking**: Monitor API usage per user with detailed statistics
- ⚡ **Rate Limiting**: Configurable rate limits to prevent abuse
- 🛡️ **Security**: Helmet, CORS, and input validation middleware

## Quick Start

### Installation

```bash
npm install
```

### Environment Variables

Create a `.env` file in the root directory:

```env
PORT=3000
OPENAI_API_KEY=your_openai_api_key_here
NODE_ENV=development
```

### Start the Server

```bash
# Development mode with auto-restart
npm run dev

# Production mode
npm start
```

The server will start on `http://localhost:3000` (or your specified PORT).

## API Documentation

### Authentication Endpoints

#### Register User
```http
POST /auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass123",
  "name": "John Doe"
}
```

#### Login
```http
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass123"
}
```

#### Get Profile
```http
GET /auth/profile
Authorization: Bearer YOUR_JWT_TOKEN
```

### OpenAI Proxy Endpoints

#### Chat Completion
```http
POST /api/chat
Authorization: Bearer YOUR_JWT_TOKEN
Content-Type: application/json

{
  "messages": [
    {
      "role": "user",
      "content": "Hello, how are you?"
    }
  ],
  "model": "gpt-3.5-turbo",
  "saveHistory": true
}
```

#### Stream Chat Completion
```http
POST /api/chat/stream
Authorization: Bearer YOUR_JWT_TOKEN
Content-Type: application/json

{
  "messages": [
    {
      "role": "user",
      "content": "Tell me a story"
    }
  ],
  "model": "gpt-3.5-turbo"
}
```

### History & Search Endpoints

#### Get Conversation History
```http
GET /api/history/:userId?limit=50
```

#### Search Conversations
```http
GET /api/search?q=search_term
Authorization: Bearer YOUR_JWT_TOKEN
```

#### Get Specific Conversation
```http
GET /api/conversation/:id
Authorization: Bearer YOUR_JWT_TOKEN
```

#### Update Conversation Title
```http
PUT /api/conversation/:id/title
Authorization: Bearer YOUR_JWT_TOKEN
Content-Type: application/json

{
  "title": "New Conversation Title"
}
```

#### User Statistics
```http
GET /api/stats
Authorization: Bearer YOUR_JWT_TOKEN
```

## Database Schema

The service uses SQLite with the following tables:

### Users
- `id` (INTEGER PRIMARY KEY)
- `email` (TEXT UNIQUE)
- `password` (TEXT, hashed)
- `profile` (TEXT, JSON)
- `tokens_used` (INTEGER)
- `created_at`, `updated_at` (DATETIME)

### Conversations
- `id` (INTEGER PRIMARY KEY)
- `user_id` (INTEGER, FK)
- `title` (TEXT)
- `created_at`, `updated_at` (DATETIME)

### Messages
- `id` (INTEGER PRIMARY KEY)
- `conversation_id` (INTEGER, FK)
- `role` (TEXT: 'user'|'assistant'|'system')
- `content` (TEXT)
- `tokens` (INTEGER)
- `created_at` (DATETIME)

## Architecture

The service follows a modular architecture with clear separation of concerns:

```
├── app.js              # Main Express application
├── auth.routes.js      # Authentication endpoints
├── openai.routes.js    # OpenAI proxy endpoints
├── database.js         # SQLite operations
├── middleware.js       # Auth & validation middleware
├── history.service.js  # Conversation management
├── package.json
└── README.md
```

## Security Features

- **Password Hashing**: bcrypt with salt rounds for secure password storage
- **JWT Authentication**: Secure token-based auth with configurable expiration
- **Rate Limiting**: Global and per-user rate limits to prevent abuse
- **Input Validation**: Comprehensive request validation middleware
- **CORS & Helmet**: Security headers and cross-origin protection

## License

MIT License - see LICENSE file for details.

