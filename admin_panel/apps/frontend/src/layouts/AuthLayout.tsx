import { Outlet, Navigate } from 'react-router-dom';
import { Box, Container, Paper, Typography } from '@mui/material';
import { useAuthStore } from '../stores/authStore';

export default function AuthLayout() {
  const { isAuthenticated } = useAuthStore();

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        bgcolor: 'background.default',
        py: 4,
      }}
    >
      <Container maxWidth="sm">
        <Paper
          elevation={0}
          sx={{
            p: 4,
            borderRadius: 3,
            bgcolor: 'background.paper',
          }}
        >
          <Box sx={{ textAlign: 'center', mb: 4 }}>
            <Typography variant="h4" fontWeight={700} gutterBottom>
              AltShop Admin
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Bot Management Panel
            </Typography>
          </Box>
          <Outlet />
        </Paper>
      </Container>
    </Box>
  );
}