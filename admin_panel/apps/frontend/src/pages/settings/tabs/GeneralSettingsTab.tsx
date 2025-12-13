import { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Box, Typography, Grid, Button, Card, CardContent,
  FormControl, InputLabel, Select, MenuItem, Divider
} from '@mui/material';
import { Save as SaveIcon } from '@mui/icons-material';
import { api } from '../../../api/client';

// Валюты
const CURRENCIES = [
  { value: 'RUB', label: '₽ Рубли (RUB)' },
  { value: 'USD', label: '$ Доллары (USD)' },
  { value: 'XTR', label: '⭐ Telegram Stars (XTR)' },
  { value: 'USDT', label: '₮ USDT' },
  { value: 'TON', label: '💎 TON' },
  { value: 'BTC', label: '₿ Bitcoin (BTC)' },
  { value: 'ETH', label: 'Ξ Ethereum (ETH)' },
  { value: 'LTC', label: 'Ł Litecoin (LTC)' },
];

interface Props {
  settings: any;
  onSuccess: (message: string) => void;
  onError: (message: string) => void;
}

export default function GeneralSettingsTab({ settings, onSuccess, onError }: Props) {
  const queryClient = useQueryClient();
  
  const [defaultCurrency, setDefaultCurrency] = useState('RUB');

  useEffect(() => {
    if (settings) {
      setDefaultCurrency(settings.defaultCurrency || 'RUB');
    }
  }, [settings]);

  const updateMutation = useMutation({
    mutationFn: async (data: any) => {
      const response = await api.patch('/settings', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
      onSuccess('Общие настройки обновлены');
    },
    onError: () => {
      onError('Ошибка обновления настроек');
    },
  });

  const handleSave = () => {
    updateMutation.mutate({ defaultCurrency });
  };

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        ⚙️ Общие настройки
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Основные настройки бота
      </Typography>

      <Grid container spacing={3}>
        {/* Валюта */}
        <Grid item xs={12} md={6}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                💰 Валюта по умолчанию
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Валюта, которая будет использоваться по умолчанию для отображения цен
              </Typography>

              <FormControl fullWidth size="small">
                <InputLabel>Валюта</InputLabel>
                <Select
                  value={defaultCurrency}
                  label="Валюта"
                  onChange={(e) => setDefaultCurrency(e.target.value)}
                >
                  {CURRENCIES.map((currency) => (
                    <MenuItem key={currency.value} value={currency.value}>
                      {currency.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </CardContent>
          </Card>
        </Grid>

        {/* Информация о системе */}
        <Grid item xs={12} md={6}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                📊 Информация о системе
              </Typography>
              
              <Box sx={{ mt: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  ID настроек
                </Typography>
                <Typography variant="body1" fontWeight={500}>
                  {settings?.id || '-'}
                </Typography>
              </Box>

              <Divider sx={{ my: 2 }} />

              <Box>
                <Typography variant="body2" color="text.secondary">
                  Режим доступа
                </Typography>
                <Typography variant="body1" fontWeight={500}>
                  {settings?.accessMode || '-'}
                </Typography>
              </Box>

              <Divider sx={{ my: 2 }} />

              <Box>
                <Typography variant="body2" color="text.secondary">
                  Требуется принятие правил
                </Typography>
                <Typography variant="body1" fontWeight={500}>
                  {settings?.rulesRequired ? 'Да' : 'Нет'}
                </Typography>
              </Box>

              <Divider sx={{ my: 2 }} />

              <Box>
                <Typography variant="body2" color="text.secondary">
                  Требуется подписка на канал
                </Typography>
                <Typography variant="body1" fontWeight={500}>
                  {settings?.channelRequired ? 'Да' : 'Нет'}
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Быстрые действия */}
        <Grid item xs={12}>
          <Card variant="outlined" sx={{ bgcolor: 'action.hover' }}>
            <CardContent>
              <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                🚀 Быстрые действия
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Часто используемые операции
              </Typography>

              <Grid container spacing={2}>
                <Grid item>
                  <Button variant="outlined" size="small">
                    📤 Экспорт настроек
                  </Button>
                </Grid>
                <Grid item>
                  <Button variant="outlined" size="small">
                    📥 Импорт настроек
                  </Button>
                </Grid>
                <Grid item>
                  <Button variant="outlined" size="small" color="warning">
                    🔄 Сбросить к умолчаниям
                  </Button>
                </Grid>
              </Grid>
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