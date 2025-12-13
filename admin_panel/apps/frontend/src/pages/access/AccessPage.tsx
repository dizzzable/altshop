import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Box,
  Typography,
  Paper,
  Grid,
  Card,
  CardActionArea,
  CardContent,
  CircularProgress,
  Alert,
  Switch,
  FormControlLabel,
  TextField,
  Button,
  Divider,
} from '@mui/material';
import { Save as SaveIcon } from '@mui/icons-material';
import { api } from '../../api/client';

const ACCESS_MODES = [
  { 
    value: 'PUBLIC', 
    emoji: '🌍', 
    label: 'Публичный', 
    description: 'Доступ разрешен для всех',
    color: '#2e7d32'
  },
  { 
    value: 'INVITED', 
    emoji: '📨', 
    label: 'По приглашению', 
    description: 'Только приглашенные пользователи',
    color: '#1976d2'
  },
  { 
    value: 'PURCHASE_BLOCKED', 
    emoji: '🚫', 
    label: 'Покупки заблокированы', 
    description: 'Покупки запрещены',
    color: '#ed6c02'
  },
  { 
    value: 'REG_BLOCKED', 
    emoji: '⛔', 
    label: 'Регистрация заблокирована', 
    description: 'Регистрация запрещена',
    color: '#d32f2f'
  },
  { 
    value: 'RESTRICTED', 
    emoji: '🔒', 
    label: 'Ограниченный', 
    description: 'Все действия полностью запрещены',
    color: '#9c27b0'
  },
];

export default function AccessPage() {
  const queryClient = useQueryClient();
  
  const [accessMode, setAccessMode] = useState('PUBLIC');
  const [rulesRequired, setRulesRequired] = useState(false);
  const [channelRequired, setChannelRequired] = useState(false);
  const [rulesLink, setRulesLink] = useState('');
  const [channelId, setChannelId] = useState('');
  const [channelLink, setChannelLink] = useState('');

  const { data: settings, isLoading, error } = useQuery({
    queryKey: ['settings'],
    queryFn: async () => {
      const response = await api.get('/settings');
      return response.data;
    },
  });

  useEffect(() => {
    if (settings) {
      setAccessMode(settings.accessMode || 'PUBLIC');
      setRulesRequired(settings.rulesRequired || false);
      setChannelRequired(settings.channelRequired || false);
      setRulesLink(settings.rulesLink || '');
      setChannelId(settings.channelId || '');
      setChannelLink(settings.channelLink || '');
    }
  }, [settings]);

  const updateAccessModeMutation = useMutation({
    mutationFn: async (mode: string) => {
      const response = await api.patch('/settings/access/mode', { accessMode: mode });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
    },
  });

  const updateConditionsMutation = useMutation({
    mutationFn: async (data: {
      rulesRequired: boolean;
      channelRequired: boolean;
      rulesLink: string;
      channelId: string;
      channelLink: string;
    }) => {
      const response = await api.patch('/settings/access/conditions', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
    },
  });

  const handleAccessModeChange = (mode: string) => {
    setAccessMode(mode);
    updateAccessModeMutation.mutate(mode);
  };

  const handleSaveConditions = () => {
    updateConditionsMutation.mutate({
      rulesRequired,
      channelRequired,
      rulesLink,
      channelId,
      channelLink,
    });
  };

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">Ошибка загрузки настроек</Alert>
      </Box>
    );
  }

  return (
    <Box>
      <Paper sx={{ p: 3, mb: 3, borderRadius: 2 }}>
        <Typography variant="h4" fontWeight={600} gutterBottom>
          🔐 Режим доступа
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Управление режимом доступа к боту
        </Typography>
      </Paper>

      {/* Access Mode Selection */}
      <Paper sx={{ p: 3, mb: 3, borderRadius: 2 }}>
        <Typography variant="h6" gutterBottom>
          Выберите режим доступа
        </Typography>
        <Grid container spacing={2} sx={{ mt: 1 }}>
          {ACCESS_MODES.map((mode) => (
            <Grid item xs={12} sm={6} md={4} key={mode.value}>
              <Card 
                sx={{ 
                  border: accessMode === mode.value ? 2 : 1,
                  borderColor: accessMode === mode.value ? mode.color : 'divider',
                  bgcolor: accessMode === mode.value ? `${mode.color}10` : 'background.paper',
                }}
              >
                <CardActionArea 
                  onClick={() => handleAccessModeChange(mode.value)}
                  sx={{ p: 2 }}
                >
                  <CardContent sx={{ textAlign: 'center' }}>
                    <Typography variant="h3" sx={{ mb: 1 }}>
                      {mode.emoji}
                    </Typography>
                    <Typography variant="h6" fontWeight={600}>
                      {mode.label}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {mode.description}
                    </Typography>
                  </CardContent>
                </CardActionArea>
              </Card>
            </Grid>
          ))}
        </Grid>
      </Paper>

      {/* Access Conditions */}
      <Paper sx={{ p: 3, borderRadius: 2 }}>
        <Typography variant="h6" gutterBottom>
          Условия доступа
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Настройте обязательные условия для пользователей
        </Typography>

        {/* Rules */}
        <Box sx={{ mb: 3 }}>
          <FormControlLabel
            control={
              <Switch
                checked={rulesRequired}
                onChange={(e) => setRulesRequired(e.target.checked)}
              />
            }
            label="📜 Требовать принятие правил"
          />
          {rulesRequired && (
            <TextField
              fullWidth
              label="Ссылка на правила"
              value={rulesLink}
              onChange={(e) => setRulesLink(e.target.value)}
              placeholder="https://telegram.org/tos/"
              sx={{ mt: 2 }}
              size="small"
            />
          )}
        </Box>

        <Divider sx={{ my: 3 }} />

        {/* Channel */}
        <Box sx={{ mb: 3 }}>
          <FormControlLabel
            control={
              <Switch
                checked={channelRequired}
                onChange={(e) => setChannelRequired(e.target.checked)}
              />
            }
            label="📢 Требовать подписку на канал"
          />
          {channelRequired && (
            <Grid container spacing={2} sx={{ mt: 1 }}>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="ID канала"
                  value={channelId}
                  onChange={(e) => setChannelId(e.target.value)}
                  placeholder="-1001234567890"
                  size="small"
                  helperText="Числовой ID канала"
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Ссылка на канал"
                  value={channelLink}
                  onChange={(e) => setChannelLink(e.target.value)}
                  placeholder="@channel_name или https://t.me/channel"
                  size="small"
                  helperText="Username или ссылка"
                />
              </Grid>
            </Grid>
          )}
        </Box>

        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 3 }}>
          <Button
            variant="contained"
            startIcon={<SaveIcon />}
            onClick={handleSaveConditions}
            disabled={updateConditionsMutation.isPending}
          >
            Сохранить условия
          </Button>
        </Box>
      </Paper>
    </Box>
  );
}