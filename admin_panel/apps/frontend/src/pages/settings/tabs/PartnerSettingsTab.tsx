import { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Box, Typography, Grid, TextField, Switch, FormControlLabel,
  Button, Divider, Card, CardContent, Chip, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, Paper
} from '@mui/material';
import { Save as SaveIcon } from '@mui/icons-material';
import { api } from '../../../api/client';

// Платежные системы с комиссиями
const PAYMENT_GATEWAYS = [
  { key: 'yookassa_commission', label: 'YooKassa', icon: '💳' },
  { key: 'telegram_stars_commission', label: 'Telegram Stars', icon: '⭐' },
  { key: 'cryptopay_commission', label: 'CryptoPay', icon: '🔐' },
  { key: 'heleket_commission', label: 'Heleket', icon: '💰' },
  { key: 'pal24_commission', label: 'Pal24', icon: '💵' },
  { key: 'wata_commission', label: 'WATA', icon: '🏦' },
  { key: 'platega_commission', label: 'Platega', icon: '💸' },
];

interface Props {
  settings: any;
  onSuccess: (message: string) => void;
  onError: (message: string) => void;
}

export default function PartnerSettingsTab({ settings, onSuccess, onError }: Props) {
  const queryClient = useQueryClient();
  
  const [partner, setPartner] = useState<any>({
    enabled: false,
    level1_percent: 10,
    level2_percent: 3,
    level3_percent: 1,
    tax_percent: 6,
    min_withdrawal_amount: 50000,
    auto_calculate_commission: true,
    yookassa_commission: 3.5,
    telegram_stars_commission: 30,
    cryptopay_commission: 1,
    heleket_commission: 1,
    pal24_commission: 5,
    wata_commission: 3,
    platega_commission: 3.5,
  });

  useEffect(() => {
    if (settings?.partner) {
      setPartner(settings.partner);
    }
  }, [settings]);

  const updatePartnerMutation = useMutation({
    mutationFn: async (data: any) => {
      const response = await api.patch('/settings/partner', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
      onSuccess('Настройки партнерской программы обновлены');
    },
    onError: () => {
      onError('Ошибка обновления настроек');
    },
  });

  const handleChange = (field: string, value: any) => {
    setPartner((prev: any) => ({ ...prev, [field]: value }));
  };

  const handleSave = () => {
    updatePartnerMutation.mutate(partner);
  };

  // Расчет минимальной суммы вывода в рублях
  const minWithdrawalRubles = (partner.min_withdrawal_amount || 0) / 100;

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        💼 Партнерская программа
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Настройте партнерскую программу с многоуровневыми комиссиями
      </Typography>

      <Grid container spacing={3}>
        {/* Основные настройки */}
        <Grid item xs={12}>
          <Card variant="outlined">
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="subtitle1" fontWeight={600}>
                  Основные настройки
                </Typography>
                <Chip 
                  label={partner.enabled ? 'Включено' : 'Выключено'} 
                  color={partner.enabled ? 'success' : 'default'}
                  size="small"
                />
              </Box>

              <FormControlLabel
                control={
                  <Switch
                    checked={partner.enabled}
                    onChange={(e) => handleChange('enabled', e.target.checked)}
                  />
                }
                label="Включить партнерскую программу"
                sx={{ mb: 2, display: 'block' }}
              />

              <Divider sx={{ my: 2 }} />

              <Typography variant="subtitle2" fontWeight={600} gutterBottom>
                📊 Проценты по уровням
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Процент от платежа реферала, который получает партнер
              </Typography>

              <Grid container spacing={2}>
                <Grid item xs={12} md={4}>
                  <TextField
                    fullWidth
                    size="small"
                    type="number"
                    label="1 уровень (%)"
                    value={partner.level1_percent}
                    onChange={(e) => handleChange('level1_percent', Number(e.target.value))}
                    disabled={!partner.enabled}
                    helperText="Прямые рефералы"
                    inputProps={{ min: 0, max: 100, step: 0.1 }}
                  />
                </Grid>
                <Grid item xs={12} md={4}>
                  <TextField
                    fullWidth
                    size="small"
                    type="number"
                    label="2 уровень (%)"
                    value={partner.level2_percent}
                    onChange={(e) => handleChange('level2_percent', Number(e.target.value))}
                    disabled={!partner.enabled}
                    helperText="Рефералы рефералов"
                    inputProps={{ min: 0, max: 100, step: 0.1 }}
                  />
                </Grid>
                <Grid item xs={12} md={4}>
                  <TextField
                    fullWidth
                    size="small"
                    type="number"
                    label="3 уровень (%)"
                    value={partner.level3_percent}
                    onChange={(e) => handleChange('level3_percent', Number(e.target.value))}
                    disabled={!partner.enabled}
                    helperText="3-й уровень рефералов"
                    inputProps={{ min: 0, max: 100, step: 0.1 }}
                  />
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        {/* Налоги и вывод */}
        <Grid item xs={12} md={6}>
          <Card variant="outlined" sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                💰 Налоги и вывод
              </Typography>

              <Grid container spacing={2}>
                <Grid item xs={12}>
                  <TextField
                    fullWidth
                    size="small"
                    type="number"
                    label="Налог (%)"
                    value={partner.tax_percent}
                    onChange={(e) => handleChange('tax_percent', Number(e.target.value))}
                    disabled={!partner.enabled}
                    helperText="Например, 6% для самозанятых"
                    inputProps={{ min: 0, max: 100, step: 0.1 }}
                  />
                </Grid>
                <Grid item xs={12}>
                  <TextField
                    fullWidth
                    size="small"
                    type="number"
                    label="Мин. сумма вывода (₽)"
                    value={minWithdrawalRubles}
                    onChange={(e) => handleChange('min_withdrawal_amount', Number(e.target.value) * 100)}
                    disabled={!partner.enabled}
                    helperText="Минимальная сумма для запроса вывода"
                    inputProps={{ min: 0, step: 100 }}
                  />
                </Grid>
                <Grid item xs={12}>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={partner.auto_calculate_commission}
                        onChange={(e) => handleChange('auto_calculate_commission', e.target.checked)}
                        disabled={!partner.enabled}
                      />
                    }
                    label="Автоматически вычитать комиссии"
                  />
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        {/* Комиссии платежных систем */}
        <Grid item xs={12} md={6}>
          <Card variant="outlined" sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                🏦 Комиссии платежных систем
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Комиссии вычитаются из суммы перед расчетом партнерского вознаграждения
              </Typography>

              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Платежная система</TableCell>
                      <TableCell align="right">Комиссия (%)</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {PAYMENT_GATEWAYS.map((gateway) => (
                      <TableRow key={gateway.key}>
                        <TableCell>
                          {gateway.icon} {gateway.label}
                        </TableCell>
                        <TableCell align="right">
                          <TextField
                            size="small"
                            type="number"
                            value={partner[gateway.key] || 0}
                            onChange={(e) => handleChange(gateway.key, Number(e.target.value))}
                            disabled={!partner.enabled}
                            inputProps={{ min: 0, max: 100, step: 0.1, style: { width: 60, textAlign: 'right' } }}
                            variant="standard"
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
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
              disabled={updatePartnerMutation.isPending}
            >
              Сохранить настройки
            </Button>
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
}