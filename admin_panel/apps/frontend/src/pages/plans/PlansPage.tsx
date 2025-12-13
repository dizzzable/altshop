import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Chip,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControlLabel,
  Switch,
  IconButton,
  Alert,
  CircularProgress,
} from '@mui/material';
import { Edit as EditIcon } from '@mui/icons-material';
import { api } from '../../api/client';

interface Plan {
  id: number;
  name: string;
  description?: string;
  trafficLimit: number;
  deviceLimit: number;
  durationDays: number;
  price: number;
  currency: string;
  type: string;
  isActive: boolean;
  isTrial: boolean;
  sortOrder: number;
}

interface PlanFormData {
  name: string;
  description: string;
  trafficLimit: number;
  deviceLimit: number;
  durationDays: number;
  price: number;
  isActive: boolean;
  isTrial: boolean;
}

export default function PlansPage() {
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingPlan, setEditingPlan] = useState<Plan | null>(null);
  const [formData, setFormData] = useState<PlanFormData>({
    name: '',
    description: '',
    trafficLimit: 0,
    deviceLimit: 1,
    durationDays: 30,
    price: 0,
    isActive: true,
    isTrial: false,
  });

  const { data: plans, isLoading, error } = useQuery({
    queryKey: ['plans'],
    queryFn: async () => {
      const response = await api.get('/plans');
      return response.data;
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: Partial<PlanFormData> }) => {
      const response = await api.patch(`/plans/${id}`, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plans'] });
      handleCloseDialog();
    },
  });

  const toggleMutation = useMutation({
    mutationFn: async (id: number) => {
      const response = await api.post(`/plans/${id}/toggle`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plans'] });
    },
  });

  const handleOpenDialog = (plan?: Plan) => {
    if (plan) {
      setEditingPlan(plan);
      setFormData({
        name: plan.name,
        description: plan.description || '',
        trafficLimit: plan.trafficLimit,
        deviceLimit: plan.deviceLimit,
        durationDays: plan.durationDays,
        price: plan.price,
        isActive: plan.isActive,
        isTrial: plan.isTrial,
      });
    } else {
      setEditingPlan(null);
      setFormData({
        name: '',
        description: '',
        trafficLimit: 0,
        deviceLimit: 1,
        durationDays: 30,
        price: 0,
        isActive: true,
        isTrial: false,
      });
    }
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setEditingPlan(null);
  };

  const handleSubmit = () => {
    if (editingPlan) {
      updateMutation.mutate({ id: editingPlan.id, data: formData });
    }
  };

  const handleToggle = (id: number) => {
    toggleMutation.mutate(id);
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
        <Alert severity="error">Ошибка загрузки планов</Alert>
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" fontWeight={600} gutterBottom>
            📋 Тарифные планы
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Управление тарифными планами подписок
          </Typography>
        </Box>
        <Alert severity="info" sx={{ maxWidth: 400 }}>
          Планы создаются через бота. Здесь можно редактировать существующие планы.
        </Alert>
      </Box>

      {plans?.length === 0 ? (
        <Alert severity="info">
          Нет тарифных планов. Создайте план через бота командой /admin.
        </Alert>
      ) : (
        <Grid container spacing={3}>
          {plans?.map((plan: Plan) => (
            <Grid item xs={12} md={6} lg={4} key={plan.id}>
              <Card sx={{ height: '100%', position: 'relative' }}>
                <CardContent>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                    <Box>
                      <Typography variant="h6" fontWeight={600}>
                        {plan.name}
                      </Typography>
                      <Typography variant="h5" color="primary" fontWeight={700}>
                        {plan.price} {plan.currency || 'RUB'}
                      </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', gap: 0.5 }}>
                      <Chip
                        label={plan.isActive ? 'Активен' : 'Неактивен'}
                        color={plan.isActive ? 'success' : 'default'}
                        size="small"
                        onClick={() => handleToggle(plan.id)}
                        sx={{ cursor: 'pointer' }}
                      />
                      {plan.isTrial && (
                        <Chip label="Пробный" color="info" size="small" />
                      )}
                    </Box>
                  </Box>

                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2, minHeight: 40 }}>
                    {plan.description || 'Без описания'}
                  </Typography>

                  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
                    <Chip
                      label={plan.trafficLimit === 0 ? '∞ Трафик' : `${plan.trafficLimit} GB`}
                      size="small"
                      variant="outlined"
                    />
                    <Chip
                      label={`${plan.deviceLimit} устр.`}
                      size="small"
                      variant="outlined"
                    />
                    <Chip
                      label={`${plan.durationDays} дней`}
                      size="small"
                      variant="outlined"
                    />
                  </Box>

                  <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
                    <IconButton size="small" onClick={() => handleOpenDialog(plan)} title="Редактировать">
                      <EditIcon fontSize="small" />
                    </IconButton>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {/* Edit Dialog */}
      <Dialog open={dialogOpen} onClose={handleCloseDialog} maxWidth="sm" fullWidth>
        <DialogTitle>
          {editingPlan ? 'Редактировать план' : 'Новый план'}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
            <TextField
              label="Название"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              fullWidth
            />
            <TextField
              label="Описание"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              fullWidth
              multiline
              rows={2}
            />
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <TextField
                  label="Цена"
                  type="number"
                  value={formData.price}
                  onChange={(e) => setFormData({ ...formData, price: Number(e.target.value) })}
                  fullWidth
                />
              </Grid>
              <Grid item xs={6}>
                <TextField
                  label="Длительность (дней)"
                  type="number"
                  value={formData.durationDays}
                  onChange={(e) => setFormData({ ...formData, durationDays: Number(e.target.value) })}
                  fullWidth
                />
              </Grid>
            </Grid>
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <TextField
                  label="Лимит трафика (GB, 0 = безлимит)"
                  type="number"
                  value={formData.trafficLimit}
                  onChange={(e) => setFormData({ ...formData, trafficLimit: Number(e.target.value) })}
                  fullWidth
                />
              </Grid>
              <Grid item xs={6}>
                <TextField
                  label="Лимит устройств"
                  type="number"
                  value={formData.deviceLimit}
                  onChange={(e) => setFormData({ ...formData, deviceLimit: Number(e.target.value) })}
                  fullWidth
                />
              </Grid>
            </Grid>
            <Box sx={{ display: 'flex', gap: 2 }}>
              <FormControlLabel
                control={
                  <Switch
                    checked={formData.isActive}
                    onChange={(e) => setFormData({ ...formData, isActive: e.target.checked })}
                  />
                }
                label="Активен"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={formData.isTrial}
                    onChange={(e) => setFormData({ ...formData, isTrial: e.target.checked })}
                  />
                }
                label="Пробный период"
              />
            </Box>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Отмена</Button>
          <Button
            onClick={handleSubmit}
            variant="contained"
            disabled={updateMutation.isPending}
          >
            {updateMutation.isPending ? 'Сохранение...' : 'Сохранить'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}