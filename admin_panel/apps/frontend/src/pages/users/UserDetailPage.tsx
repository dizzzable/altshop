import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Chip,
  Button,
  Divider,
  Skeleton,
} from '@mui/material';
import { ArrowBack as BackIcon } from '@mui/icons-material';
import { api } from '../../api/client';

export default function UserDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const { data: user, isLoading } = useQuery({
    queryKey: ['user', id],
    queryFn: async () => {
      const response = await api.get(`/users/${id}`);
      return response.data;
    },
  });

  if (isLoading) {
    return (
      <Box>
        <Skeleton variant="text" width={200} height={40} />
        <Skeleton variant="rectangular" height={300} sx={{ mt: 2 }} />
      </Box>
    );
  }

  return (
    <Box>
      <Button
        startIcon={<BackIcon />}
        onClick={() => navigate('/users')}
        sx={{ mb: 2 }}
      >
        Back to Users
      </Button>

      <Typography variant="h4" fontWeight={600} gutterBottom>
        User Details
      </Typography>

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Basic Information
              </Typography>
              <Divider sx={{ mb: 2 }} />
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Telegram ID
                  </Typography>
                  <Typography variant="body1">{user?.telegramId}</Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Username
                  </Typography>
                  <Typography variant="body1">
                    {user?.username ? `@${user.username}` : '-'}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Name
                  </Typography>
                  <Typography variant="body1">{user?.name}</Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Role
                  </Typography>
                  <Box>
                    <Chip label={user?.role} size="small" color="primary" />
                  </Box>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Status
                  </Typography>
                  <Box>
                    <Chip
                      label={user?.isBlocked ? 'Blocked' : 'Active'}
                      size="small"
                      color={user?.isBlocked ? 'error' : 'success'}
                    />
                  </Box>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Account Details
              </Typography>
              <Divider sx={{ mb: 2 }} />
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Points
                  </Typography>
                  <Typography variant="body1">{user?.points}</Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Personal Discount
                  </Typography>
                  <Typography variant="body1">{user?.personalDiscount}%</Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Purchase Discount
                  </Typography>
                  <Typography variant="body1">{user?.purchaseDiscount}%</Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Referral Code
                  </Typography>
                  <Typography variant="body1">{user?.referralCode}</Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Registered
                  </Typography>
                  <Typography variant="body1">
                    {user?.createdAt && new Date(user.createdAt).toLocaleString()}
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}