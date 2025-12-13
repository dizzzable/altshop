import { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Box, Typography, Grid, Switch, FormControlLabel,
  Button, Divider, Card, CardContent, Chip
} from '@mui/material';
import { Save as SaveIcon } from '@mui/icons-material';
import { api } from '../../../api/client';

// Типы уведомлений пользователей
const USER_NOTIFICATIONS = [
  { key: 'expires_in_3_days', label: 'Истекает через 3 дня', icon: '⏰' },
  { key: 'expires_in_2_days', label: 'Истекает через 2 дня', icon: '⏰' },
  { key: 'expires_in_1_days', label: 'Истекает через 1 день', icon: '⏰' },
  { key: 'expired', label: 'Подписка истекла', icon: '❌' },
  { key: 'limited', label: 'Лимит трафика', icon: '📊' },
  { key: 'expired_1_day_ago', label: 'Истекла 1 день назад', icon: '📅' },
  { key: 'referral_attached', label: 'Реферал присоединился', icon: '👥' },
  { key: 'referral_reward', label: 'Реферальная награда', icon: '🎁' },
];

// Типы системных уведомлений
const SYSTEM_NOTIFICATIONS = [
  { key: 'bot_lifetime', label: 'Время работы бота', icon: '🤖' },
  { key: 'bot_update', label: 'Обновление бота', icon: '🔄' },
  { key: 'user_registered', label: 'Новый пользователь', icon: '👤' },
  { key: 'subscription', label: 'Новая подписка', icon: '💳' },
  { key: 'promocode_activated', label: 'Промокод активирован', icon: '🎟️' },
  { key: 'trial_getted', label: 'Триал получен', icon: '🆓' },
  { key: 'node_status', label: 'Статус ноды', icon: '🖥️' },
  { key: 'user_first_connected', label: 'Первое подключение', icon: '🔗' },
  { key: 'user_hwid', label: 'HWID пользователя', icon: '🔐' },
];

interface Props {
  settings: any;
  onSuccess: (message: string) => void;
  onError: (message: string) => void;
}

export default function NotificationsSettingsTab({ settings, onSuccess, onError }: Props) {
  const queryClient = useQueryClient();
  
  const [userNotifications, setUserNotifications] = useState<Record<string, boolean>>({});
  const [systemNotifications, setSystemNotifications] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (settings) {
      setUserNotifications(settings.userNotifications || {});
      setSystemNotifications(settings.systemNotifications || {});
    }
  }, [settings]);

  const updateUserNotificationsMutation = useMutation({
    mutationFn: async (data: Record<string, boolean>) => {
      const response = await api.patch('/settings/notifications/user', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
      onSuccess('Уведомления пользователей обновлены');
    },
    onError: () => {
      onError('Ошибка обновления уведомлений');
    },
  });

  const updateSystemNotificationsMutation = useMutation({
    mutationFn: async (data: Record<string, boolean>) => {
      const response = await api.patch('/settings/notifications/system', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
      onSuccess('Системные уведомления обновлены');
    },
    onError: () => {
      onError('Ошибка обновления уведомлений');
    },
  });

  const handleUserNotificationChange = (key: string, value: boolean) => {
    setUserNotifications((prev) => ({ ...prev, [key]: value }));
  };

  const handleSystemNotificationChange = (key: string, value: boolean) => {
    setSystemNotifications((prev) => ({ ...prev, [key]: value }));
  };

  const handleSaveUserNotifications = () => {
    updateUserNotificationsMutation.mutate(userNotifications);
  };

  const handleSaveSystemNotifications = () => {
    updateSystemNotificationsMutation.mutate(systemNotifications);
  };

  const enabledUserCount = Object.values(userNotifications).filter(Boolean).length;
  const enabledSystemCount = Object.values(systemNotifications).filter(Boolean).length;

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        🔔 Уведомления
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Настройте уведомления для пользователей и администраторов
      </Typography>

      <Grid container spacing={3}>
        {/* Уведомления пользователей */}
        <Grid item xs={12} md={6}>
          <Card variant="outlined">
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="subtitle1" fontWeight={600}>
                  👤 Уведомления пользователей
                </Typography>
                <Chip 
                  label={`${enabledUserCount}/${USER_NOTIFICATIONS.length}`} 
                  size="small" 
                  color={enabledUserCount > 0 ? 'primary' : 'default'}
                />
              </Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Уведомления, которые получают пользователи
              </Typography>

              <Divider sx={{ my: 2 }} />

              {USER_NOTIFICATIONS.map((notification) => (
                <FormControlLabel
                  key={notification.key}
                  control={
                    <Switch
                      checked={userNotifications[notification.key] ?? true}
                      onChange={(e) => handleUserNotificationChange(notification.key, e.target.checked)}
                      size="small"
                    />
                  }
                  label={
                    <Typography variant="body2">
                      {notification.icon} {notification.label}
                    </Typography>
                  }
                  sx={{ display: 'block', mb: 1 }}
                />
              ))}

              <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 3 }}>
                <Button
                  variant="contained"
                  size="small"
                  startIcon={<SaveIcon />}
                  onClick={handleSaveUserNotifications}
                  disabled={updateUserNotificationsMutation.isPending}
                >
                  Сохранить
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Системные уведомления */}
        <Grid item xs={12} md={6}>
          <Card variant="outlined">
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="subtitle1" fontWeight={600}>
                  🖥️ Системные уведомления
                </Typography>
                <Chip 
                  label={`${enabledSystemCount}/${SYSTEM_NOTIFICATIONS.length}`} 
                  size="small" 
                  color={enabledSystemCount > 0 ? 'primary' : 'default'}
                />
              </Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Уведомления для администраторов
              </Typography>

              <Divider sx={{ my: 2 }} />

              {SYSTEM_NOTIFICATIONS.map((notification) => (
                <FormControlLabel
                  key={notification.key}
                  control={
                    <Switch
                      checked={systemNotifications[notification.key] ?? true}
                      onChange={(e) => handleSystemNotificationChange(notification.key, e.target.checked)}
                      size="small"
                    />
                  }
                  label={
                    <Typography variant="body2">
                      {notification.icon} {notification.label}
                    </Typography>
                  }
                  sx={{ display: 'block', mb: 1 }}
                />
              ))}

              <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 3 }}>
                <Button
                  variant="contained"
                  size="small"
                  startIcon={<SaveIcon />}
                  onClick={handleSaveSystemNotifications}
                  disabled={updateSystemNotificationsMutation.isPending}
                >
                  Сохранить
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}