import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  TextField,
  Button,
  Alert,
  InputAdornment,
  IconButton,
  Divider,
  Typography,
} from '@mui/material';
import { Visibility, VisibilityOff, DeveloperMode } from '@mui/icons-material';
import { useAuthStore } from '../../stores/authStore';

const isDev = import.meta.env.DEV || import.meta.env.MODE === 'development';

export default function LoginPage() {
  const navigate = useNavigate();
  const { login, devLogin, isLoading, error } = useAuthStore();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await login(username, password);
      navigate('/dashboard');
    } catch {
      // Error is handled in store
    }
  };

  return (
    <Box component="form" onSubmit={handleSubmit}>
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}
      <TextField
        fullWidth
        label="Username"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        margin="normal"
        required
        autoFocus
      />
      <TextField
        fullWidth
        label="Password"
        type={showPassword ? 'text' : 'password'}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        margin="normal"
        required
        InputProps={{
          endAdornment: (
            <InputAdornment position="end">
              <IconButton
                onClick={() => setShowPassword(!showPassword)}
                edge="end"
              >
                {showPassword ? <VisibilityOff /> : <Visibility />}
              </IconButton>
            </InputAdornment>
          ),
        }}
      />
      <Button
        type="submit"
        fullWidth
        variant="contained"
        size="large"
        disabled={isLoading}
        sx={{ mt: 3 }}
      >
        {isLoading ? 'Signing in...' : 'Sign In'}
      </Button>
      
      {isDev && (
        <>
          <Divider sx={{ my: 3 }}>
            <Typography variant="body2" color="text.secondary">
              Development Mode
            </Typography>
          </Divider>
          <Button
            fullWidth
            variant="outlined"
            size="large"
            startIcon={<DeveloperMode />}
            onClick={() => {
              devLogin();
              navigate('/dashboard');
            }}
            sx={{ mt: 1 }}
          >
            Dev Login (без пароля)
          </Button>
          <Alert severity="info" sx={{ mt: 2 }}>
            В режиме разработки можно войти с любыми данными или использовать кнопку Dev Login
          </Alert>
        </>
      )}
    </Box>
  );
}