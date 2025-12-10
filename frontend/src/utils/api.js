import axios from 'axios';

// Try to get API URL from runtime config (set by entrypoint script)
// Falls back to build-time env var, then to localhost
let API_BASE_URL = 'http://localhost:8000';

// Check for runtime config (injected by entrypoint script)
try {
  // This will be available at runtime if entrypoint script creates it
  const runtimeConfig = window.__RUNTIME_CONFIG__;
  if (runtimeConfig && runtimeConfig.VITE_API_BASE_URL) {
    API_BASE_URL = runtimeConfig.VITE_API_BASE_URL;
    console.log('Using runtime API URL:', API_BASE_URL);
  } else if (import.meta.env.VITE_API_BASE_URL) {
    API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
    console.log('Using build-time API URL:', API_BASE_URL);
  } else {
    console.warn('No API URL configured, using default:', API_BASE_URL);
  }
} catch (e) {
  // Fallback to build-time env var
  if (import.meta.env.VITE_API_BASE_URL) {
    API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
    console.log('Using build-time API URL (fallback):', API_BASE_URL);
  } else {
    console.warn('No API URL configured, using default:', API_BASE_URL);
  }
}

// Create axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token and log requests
api.interceptors.request.use(
  (config) => {
    // Log the full URL being requested for debugging
    const fullUrl = config.baseURL + config.url;
    console.log(`[API Request] ${config.method?.toUpperCase()} ${fullUrl}`);
    console.log(`[API Config] baseURL: ${config.baseURL}, url: ${config.url}`);
    
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    } else {
      console.warn('No access token found in localStorage for request to:', config.url);
    }
    return config;
  },
  (error) => {
    console.error('[API Request Error]', error);
    return Promise.reject(error);
  }
);

// Response interceptor to handle errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Log detailed error information for debugging
    if (error.request) {
      console.error('[API Error] Request made but no response received');
      console.error('[API Error] Request URL:', error.config?.url);
      console.error('[API Error] Base URL:', error.config?.baseURL);
      console.error('[API Error] Full URL:', error.config?.baseURL + error.config?.url);
      console.error('[API Error] Error details:', error.message);
    } else if (error.response) {
      console.error('[API Error] Server responded with error:', error.response.status);
      console.error('[API Error] Response data:', error.response.data);
    } else {
      console.error('[API Error] Request setup failed:', error.message);
    }
    
    if (error.response?.status === 401) {
      // Token expired or invalid - only redirect if not already on login/register page
      const currentPath = window.location.pathname;
      if (!currentPath.includes('/login') && !currentPath.includes('/register')) {
        console.warn('401 Unauthorized - redirecting to login');
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authAPI = {
  register: async (email, password, fullName) => {
    const response = await api.post('/api/auth/register', {
      email,
      password,
      full_name: fullName,
    });
    return response.data;
  },

  login: async (email, password) => {
    const response = await api.post('/api/auth/login', {
      email,
      password,
    });
    return response.data;
  },

  getMe: async () => {
    const response = await api.get('/api/auth/me');
    return response.data;
  },
};

// Query API
export const queryAPI = {
  query: async (query) => {
    const response = await api.post('/api/query', { query });
    return response.data;
  },

  queryStream: async function* (query, onMetadata) {
    const token = localStorage.getItem('access_token');
    const headers = {
      'Content-Type': 'application/json',
    };
    
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE_URL}/api/query/stream`, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify({ query }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    try {
      let buffer = '';
      
      while (true) {
        const { done, value } = await reader.read();
        
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // Keep incomplete line in buffer
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              if (data.type === 'metadata' && onMetadata) {
                onMetadata(data.data);
              } else if (data.type === 'token') {
                yield data.data;
              } else if (data.type === 'error') {
                throw new Error(data.data.message || 'An error occurred');
              } else if (data.type === 'done') {
                return;
              }
            } catch (e) {
              // If JSON parsing fails, it might be a non-JSON line, skip it
              if (e instanceof SyntaxError) {
                continue;
              }
              console.error('Error parsing SSE data:', e);
              throw e;
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  },
};

export default api;

