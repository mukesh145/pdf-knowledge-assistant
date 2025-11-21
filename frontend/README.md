# PDF Knowledge Assistant - Frontend

React SPA frontend for the PDF Knowledge Assistant application.

## Features

- 🔐 User authentication (Login/Register)
- 💬 Chat interface for querying PDF documents
- 👤 User profile management
- 🔒 Protected routes
- 🎨 Modern UI with Tailwind CSS

## Setup

1. Install dependencies:
```bash
npm install
```

2. Create a `.env` file (or copy from `.env.example`):
```bash
VITE_API_BASE_URL=http://localhost:8000
```

3. Start the development server:
```bash
npm run dev
```

The app will be available at `http://localhost:5173` (or the port Vite assigns).

## Build for Production

```bash
npm run build
```

The built files will be in the `dist` directory.

## Project Structure

```
src/
├── components/       # Reusable components
│   ├── Layout.jsx    # Main layout with header
│   └── ProtectedRoute.jsx  # Route protection
├── contexts/         # React contexts
│   └── AuthContext.jsx     # Authentication state
├── pages/            # Page components
│   ├── Login.jsx     # Login page
│   ├── Register.jsx  # Registration page
│   ├── Chat.jsx      # Main chat interface
│   └── Profile.jsx   # User profile page
├── utils/            # Utility functions
│   └── api.js        # API client with JWT handling
├── App.jsx           # Main app component with routing
└── main.jsx          # Entry point
```

## API Integration

The frontend communicates with the FastAPI backend at the URL specified in `VITE_API_BASE_URL`. 

### Authentication Flow

1. User registers/logs in via `/auth/register` or `/auth/login`
2. JWT token is stored in `localStorage`
3. Token is automatically included in all API requests via axios interceptors
4. On 401 errors, user is redirected to login

### Endpoints Used

- `POST /auth/register` - User registration
- `POST /auth/login` - User login
- `GET /auth/me` - Get current user info
- `POST /query` - Query the knowledge assistant
