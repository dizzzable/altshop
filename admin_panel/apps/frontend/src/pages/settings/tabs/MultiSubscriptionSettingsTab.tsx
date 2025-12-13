import { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Box, Typography, Grid, TextField, Switch, FormControlLabel,
  Button, Card, CardContent, Chip, Slider, Alert
} from '@mui/material';
import { Save as SaveIcon } from '@mui/icons-material';
import { api } from '../../../api/client';

interface Props {
  settings: any;
  onSuccess: (message: string) => void;
  onError: (message: string) => void;
}

export default function MultiSubscriptionSettingsTab({ settings, onSuccess, onError }: Props) {
  const queryClient = useQueryClient();
  
  const [multiSubscription, setMultiSubscription] = useState<any>({
    enabled: true,
    default_max_subscriptions: 5,
  });

  useEffect(() => {
    if (settings?.multiSubscription) {
      setMultiSubscription(settings.multiSubscription);
    }
  }, [settings]);

  const updateMutation = useMutation({
    mutationFn: async (data: any) => {
      const response = await api.patch('/settings/multi-subscription', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
      onSuccess('Настройки мультиподписки обновлены');
    },
    onError: () => {
      onError('Ошибка обновления настроек');
    },
  });

  const handleChange = (field: string, value: any) => {
    setMultiSubscription((prev: any) => ({ ...prev, [field]: value }));
  };

  const handleSave = () => {
    updateMutation.mutate(multiSubscription);
  };

  const marks = [
    { value: 1, label: '1' },
    { value: 3, label: '3' },
    { value: 5, label: '5' },
    { value: 10, label: '10' },
    { value: 15, label: '15' },
    { value: 20, label: '20' },
  ];

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        📦 Мультиподписка
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Настройте возможность иметь несколько активных подписок одновременно
      </Typography>

      <Grid container spacing={3}>
        <Grid item xs={12}>
          <Card variant="outlined">
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="subtitle1" fontWeight={600}>
                  Настройки мультиподписки
                </Typography>
                <Chip 
                  label={multiSubscription.enabled ? 'Включено' : 'Выключено'} 
                  color={multiSubscription.enabled ? 'success' : 'default'}
                  size="small"
                />
              </Box>

              <FormControlLabel
                control={
                  <Switch
                    checked={multiSubscription.enabled}
                    onChange={(e) => handleChange('enabled', e.target.checked)}
                  />
                }
                label="Разрешить мультиподписки"
                sx={{ mb: 3, display: 'block' }}
              />

              {multiSubscription.enabled && (
                <>
                  <Typography variant="subtitle2" gutterBottom>
                    Максимальное количество подписок
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Сколько активных подписок может иметь один пользователь
                  </Typography>

                  <Box sx={{ px: 2, mb: 3 }}>
                    <Slider
                      value={multiSubscription.default_max_subscriptions}
                      onChange={(_e, value) => handleChange('default_max_subscriptions', value)}
                      min={1}
                      max={20}
                      marks={marks}
                      valueLabelDisplay="on"
                    />
                  </Box>

                  <TextField
                    fullWidth
                    size="small"
                    type="number"
                    label="Точное значение"
                    value={multiSubscription.default_max_subscriptions}
                    onChange={(e) => handleChange('default_max_subscriptions', Number(e.target.value))}
                    inputProps={{ min: 1, max: 100 }}
                    helperText="Введите число от 1 до 100"
                  />
                </>
              )}

              {!multiSubscription.enabled && (
                <Alert severity="info" sx={{ mt: 2 }}>
                  Когда мультиподписки отключены, пользователи могут иметь только одну активную подписку.
                  При покупке новой подписки старая будет заменена.
                </Alert>
              )}

              {multiSubscription.enabled && multiSubscription.default_max_subscriptions === 1 && (
                <Alert severity="warning" sx={{ mt: 2 }}>
                  При значении 1 мультиподписки фактически отключены - пользователь может иметь только одну подписку.
                </Alert>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Информация */}
        <Grid item xs={12}>
          <Card variant="outlined" sx={{ bgcolor: 'action.hover' }}>
            <CardContent>
              <Typography variant="subtitle2" fontWeight={600} gutterBottom>
                ℹ️ Как это работает
              </Typography>
              <Typography variant="body2" color="text.secondary">
                • Мультиподписка позволяет пользователям иметь несколько активных подписок одновременно
              </Typography>
              <Typography variant="body2" color="text.secondary">
                • Каждая подписка может быть на разный тариф или с разными параметрами
              </Typography>
              <Typography variant="body2" color="text.secondary">
                • Полезно для пользователей, которым нужно несколько конфигураций VPN
              </Typography>
              <Typography variant="body2" color="text.secondary">
                • Лимит можно изменить индивидуально для каждого пользователя
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Кнопка сохранения */}
        <Grid item xs={12}>
          <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
            <Button
              variant="contained"
              startIcon={<SaveIcon />}
              onClick={handleSave}
              disabled={updateMutation.isPending}
            >
              Сохранить настройки
            </Button>
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
}