import { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Box, Typography, Grid, TextField, Switch, FormControlLabel,
  Button, Card, CardContent, Select, MenuItem, FormControl,
  InputLabel, Accordion, AccordionSummary, AccordionDetails, Chip
} from '@mui/material';
import { Save as SaveIcon, ExpandMore as ExpandMoreIcon } from '@mui/icons-material';
import { api } from '../../../api/client';

// Типы наград
const REWARD_TYPES = [
  { value: 'POINTS', label: '🎯 Баллы' },
  { value: 'EXTRA_DAYS', label: '📅 Дополнительные дни' },
];

// Уровни реферальной программы
const REFERRAL_LEVELS = [
  { value: 1, label: '1 уровень' },
  { value: 2, label: '2 уровня' },
  { value: 3, label: '3 уровня' },
];

// Стратегии начисления
const ACCRUAL_STRATEGIES = [
  { value: 'ON_FIRST_PAYMENT', label: 'При первой оплате' },
  { value: 'ON_EACH_PAYMENT', label: 'При каждой оплате' },
];

// Стратегии расчета награды
const REWARD_STRATEGIES = [
  { value: 'AMOUNT', label: 'Фиксированная сумма' },
  { value: 'PERCENT', label: 'Процент от платежа' },
];

interface Props {
  settings: any;
  onSuccess: (message: string) => void;
  onError: (message: string) => void;
}

export default function ReferralSettingsTab({ settings, onSuccess, onError }: Props) {
  const queryClient = useQueryClient();
  
  const [referral, setReferral] = useState<any>({
    enable: true,
    level: 1,
    accrual_strategy: 'ON_FIRST_PAYMENT',
    reward: {
      type: 'EXTRA_DAYS',
      strategy: 'AMOUNT',
      config: { 1: 5 },
    },
    eligible_plan_ids: [],
    points_exchange: {
      exchange_enabled: true,
      points_per_day: 1,
      min_exchange_points: 1,
      max_exchange_points: -1,
    },
  });

  useEffect(() => {
    if (settings?.referral) {
      setReferral(settings.referral);
    }
  }, [settings]);

  const updateReferralMutation = useMutation({
    mutationFn: async (data: any) => {
      const response = await api.patch('/settings/referral', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
      onSuccess('Настройки реферальной программы обновлены');
    },
    onError: () => {
      onError('Ошибка обновления настроек');
    },
  });

  const handleChange = (field: string, value: any) => {
    setReferral((prev: any) => ({ ...prev, [field]: value }));
  };

  const handleRewardChange = (field: string, value: any) => {
    setReferral((prev: any) => ({
      ...prev,
      reward: { ...prev.reward, [field]: value },
    }));
  };

  const handleRewardConfigChange = (level: number, value: number) => {
    setReferral((prev: any) => ({
      ...prev,
      reward: {
        ...prev.reward,
        config: { ...prev.reward.config, [level]: value },
      },
    }));
  };

  const handlePointsExchangeChange = (field: string, value: any) => {
    setReferral((prev: any) => ({
      ...prev,
      points_exchange: { ...prev.points_exchange, [field]: value },
    }));
  };

  const handleSave = () => {
    updateReferralMutation.mutate(referral);
  };

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        👥 Реферальная система
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Настройте реферальную программу для привлечения новых пользователей
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
                  label={referral.enable ? 'Включено' : 'Выключено'} 
                  color={referral.enable ? 'success' : 'default'}
                  size="small"
                />
              </Box>

              <FormControlLabel
                control={
                  <Switch
                    checked={referral.enable}
                    onChange={(e) => handleChange('enable', e.target.checked)}
                  />
                }
                label="Включить реферальную программу"
                sx={{ mb: 2, display: 'block' }}
              />

              <Grid container spacing={2}>
                <Grid item xs={12} md={4}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Уровни рефералов</InputLabel>
                    <Select
                      value={referral.level}
                      label="Уровни рефералов"
                      onChange={(e) => handleChange('level', e.target.value)}
                      disabled={!referral.enable}
                    >
                      {REFERRAL_LEVELS.map((level) => (
                        <MenuItem key={level.value} value={level.value}>
                          {level.label}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>

                <Grid item xs={12} md={4}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Стратегия начисления</InputLabel>
                    <Select
                      value={referral.accrual_strategy}
                      label="Стратегия начисления"
                      onChange={(e) => handleChange('accrual_strategy', e.target.value)}
                      disabled={!referral.enable}
                    >
                      {ACCRUAL_STRATEGIES.map((strategy) => (
                        <MenuItem key={strategy.value} value={strategy.value}>
                          {strategy.label}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>

                <Grid item xs={12} md={4}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Тип награды</InputLabel>
                    <Select
                      value={referral.reward?.type || 'EXTRA_DAYS'}
                      label="Тип награды"
                      onChange={(e) => handleRewardChange('type', e.target.value)}
                      disabled={!referral.enable}
                    >
                      {REWARD_TYPES.map((type) => (
                        <MenuItem key={type.value} value={type.value}>
                          {type.label}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        {/* Настройки награды */}
        <Grid item xs={12}>
          <Accordion defaultExpanded disabled={!referral.enable}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography fontWeight={600}>🎁 Настройки награды</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Grid container spacing={2}>
                <Grid item xs={12} md={6}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Стратегия расчета</InputLabel>
                    <Select
                      value={referral.reward?.strategy || 'AMOUNT'}
                      label="Стратегия расчета"
                      onChange={(e) => handleRewardChange('strategy', e.target.value)}
                    >
                      {REWARD_STRATEGIES.map((strategy) => (
                        <MenuItem key={strategy.value} value={strategy.value}>
                          {strategy.label}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>

                {[1, 2, 3].slice(0, referral.level).map((level) => (
                  <Grid item xs={12} md={4} key={level}>
                    <TextField
                      fullWidth
                      size="small"
                      type="number"
                      label={`Награда за ${level} уровень`}
                      value={referral.reward?.config?.[level] || 0}
                      onChange={(e) => handleRewardConfigChange(level, Number(e.target.value))}
                      helperText={referral.reward?.strategy === 'PERCENT' ? '%' : referral.reward?.type === 'POINTS' ? 'баллов' : 'дней'}
                    />
                  </Grid>
                ))}
              </Grid>
            </AccordionDetails>
          </Accordion>
        </Grid>

        {/* Обмен баллов */}
        {referral.reward?.type === 'POINTS' && (
          <Grid item xs={12}>
            <Accordion disabled={!referral.enable}>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Typography fontWeight={600}>💱 Обмен баллов</Typography>
              </AccordionSummary>
              <AccordionDetails>
                <FormControlLabel
                  control={
                    <Switch
                      checked={referral.points_exchange?.exchange_enabled ?? true}
                      onChange={(e) => handlePointsExchangeChange('exchange_enabled', e.target.checked)}
                    />
                  }
                  label="Разрешить обмен баллов"
                  sx={{ mb: 2, display: 'block' }}
                />

                <Grid container spacing={2}>
                  <Grid item xs={12} md={4}>
                    <TextField
                      fullWidth
                      size="small"
                      type="number"
                      label="Баллов за 1 день"
                      value={referral.points_exchange?.points_per_day || 1}
                      onChange={(e) => handlePointsExchangeChange('points_per_day', Number(e.target.value))}
                      disabled={!referral.points_exchange?.exchange_enabled}
                    />
                  </Grid>
                  <Grid item xs={12} md={4}>
                    <TextField
                      fullWidth
                      size="small"
                      type="number"
                      label="Мин. баллов для обмена"
                      value={referral.points_exchange?.min_exchange_points || 1}
                      onChange={(e) => handlePointsExchangeChange('min_exchange_points', Number(e.target.value))}
                      disabled={!referral.points_exchange?.exchange_enabled}
                    />
                  </Grid>
                  <Grid item xs={12} md={4}>
                    <TextField
                      fullWidth
                      size="small"
                      type="number"
                      label="Макс. баллов за раз (-1 = без лимита)"
                      value={referral.points_exchange?.max_exchange_points ?? -1}
                      onChange={(e) => handlePointsExchangeChange('max_exchange_points', Number(e.target.value))}
                      disabled={!referral.points_exchange?.exchange_enabled}
                    />
                  </Grid>
                </Grid>
              </AccordionDetails>
            </Accordion>
          </Grid>
        )}

        {/* Кнопка сохранения */}
        <Grid item xs={12}>
          <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
            <Button
              variant="contained"
              startIcon={<SaveIcon />}
              onClick={handleSave}
              disabled={updateReferralMutation.isPending}
            >
              Сохранить настройки
            </Button>
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
}