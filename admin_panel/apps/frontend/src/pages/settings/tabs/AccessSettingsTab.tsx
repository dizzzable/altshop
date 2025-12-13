import { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Box, Typography, Grid, TextField, Switch, FormControlLabel,
  Button, Divider, Card, CardContent, ToggleButton, ToggleButtonGroup
} from '@mui/material';
import { Save as SaveIcon } from '@mui/icons-material';
import { api } from '../../../api/client';

// Режимы доступа
const ACCESS_MODES = [
  { value: 'PUBLIC', label: '🌍 Публичный', description: 'Доступ разрешен для всех' },
  { value: 'INVITED', label: '📨 По приглашению', description: 'Только приглашенные пользователи' },
  { value: 'PURCHASE_BLOCKED', label: '🚫 Покупки заблокированы', description: 'Покупки запрещены' },
  { value: 'REG_BLOCKED', label: '⛔ Регистрация заблокирована', description: 'Регистрация запрещена' },
  { value: 'RESTRICTED', label: '🔒 Ограниченный', description: 'Все действия полностью запрещены' },
];

interface Props {
  settings: any;
  onSuccess: (message: string) => void;
  onError: (message: string) => void;
}

export default function AccessSettingsTab({ settings, onSuccess, onError }: Props) {
  const queryClient = useQueryClient();
  
  const [accessMode, setAccessMode] = useState(settings?.accessMode || 'PUBLIC');
  const [rulesRequired, setRulesRequired] = useState(settings?.rulesRequired || false);
  const [channelRequired, setChannelRequired] = useState(settings?.channelRequired || false);
  const [rulesLink, setRulesLink] = useState(settings?.rulesLink || '');
  const [channelId, setChannelId] = useState(settings?.channelId || '');
  const [channelLink, setChannelLink] = useState(settings?.channelLink || '');

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
      onSuccess('Режим доступа обновлен');
    },
    onError: () => {
      onError('Ошибка обновления режима доступа');
    },
  });

  const updateConditionsMutation = useMutation({
    mutationFn: async (data: any) => {
      const response = await api.patch('/settings/access/conditions', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
      onSuccess('Условия доступа обновлены');
    },
    onError: () => {
      onError('Ошибка обновления условий доступа');
    },
  });

  const handleAccessModeChange = (_event: React.MouseEvent<HTMLElement>, newMode: string | null) => {
    if (newMode) {
      setAccessMode(newMode);
      updateAccessModeMutation.mutate(newMode);
    }
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

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        🔐 Режим доступа
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Выберите режим доступа к боту
      </Typography>

      <Grid container spacing={3}>
        {/* Режим доступа */}
        <Grid item xs={12}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                Текущий режим
              </Typography>
              <ToggleButtonGroup
                value={accessMode}
                exclusive
                onChange={handleAccessModeChange}
                orientation="vertical"
                fullWidth
                sx={{ mt: 2 }}
              >
                {ACCESS_MODES.map((mode) => (
                  <ToggleButton 
                    key={mode.value} 
                    value={mode.value}
                    sx={{ 
                      justifyContent: 'flex-start', 
                      textAlign: 'left',
                      py: 2,
                      px: 3
                    }}
                  >
                    <Box>
                      <Typography variant="body1" fontWeight={500}>
                        {mode.label}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {mode.description}
                      </Typography>
                    </Box>
                  </ToggleButton>
                ))}
              </ToggleButtonGroup>
            </CardContent>
          </Card>
        </Grid>

        {/* Условия доступа */}
        <Grid item xs={12}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                Условия доступа
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Настройте обязательные условия для пользователей
              </Typography>

              <Divider sx={{ my: 2 }} />

              {/* Правила */}
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

              <Divider sx={{ my: 2 }} />

              {/* Канал */}
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
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}