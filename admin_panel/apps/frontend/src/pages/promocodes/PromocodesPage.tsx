import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Box,
  Typography,
  Card,
  Chip,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControlLabel,
  Switch,
  MenuItem,
  Select,
  InputLabel,
  FormControl,
  IconButton,
  Grid,
} from '@mui/material';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  ToggleOn as ToggleIcon,
} from '@mui/icons-material';
import { api } from '../../api/client';

interface Promocode {
  id: number;
  code: string;
  type: string;
  discount: number;
  bonusDays: number;
  maxActivations: number;
  currentActivations: number;
  isActive: boolean;
  validFrom?: string;
  validUntil?: string;
  planIds?: number[];
  createdAt: string;
}

interface PromocodeFormData {
  code: string;
  type: string;
  discount: number;
  bonusDays: number;
  maxActivations: number;
  isActive: boolean;
  validUntil: string;
}

const PROMOCODE_TYPES = [
  { value: 'discount', label: 'Скидка' },
  { value: 'bonus', label: 'Бонусные дни' },
  { value: 'trial', label: 'Пробный период' },
];

export default function PromocodesPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingPromocode, setEditingPromocode] = useState<Promocode | null>(null);
  const [formData, setFormData] = useState<PromocodeFormData>({
    code: '',
    type: 'discount',
    discount: 10,
    bonusDays: 0,
    maxActivations: 100,
    isActive: true,
    validUntil: '',
  });

  const { data, isLoading } = useQuery({
    queryKey: ['promocodes', page, pageSize],
    queryFn: async () => {
      const response = await api.get('/promocodes', { params: { page: page + 1, limit: pageSize } });
      return response.data;
    },
  });

  const createMutation = useMutation({
    mutationFn: async (data: PromocodeFormData) => {
      const response = await api.post('/promocodes', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['promocodes'] });
      handleCloseDialog();
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: Partial<PromocodeFormData> }) => {
      const response = await api.patch(`/promocodes/${id}`, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['promocodes'] });
      handleCloseDialog();
    },
  });

  const toggleMutation = useMutation({
    mutationFn: async (id: number) => {
      const response = await api.post(`/promocodes/${id}/toggle`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['promocodes'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/promocodes/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['promocodes'] });
    },
  });

  const handleOpenDialog = (promocode?: Promocode) => {
    if (promocode) {
      setEditingPromocode(promocode);
      setFormData({
        code: promocode.code,
        type: promocode.type,
        discount: promocode.discount,
        bonusDays: promocode.bonusDays,
        maxActivations: promocode.maxActivations,
        isActive: promocode.isActive,
        validUntil: promocode.validUntil ? promocode.validUntil.split('T')[0] : '',
      });
    } else {
      setEditingPromocode(null);
      setFormData({
        code: generateRandomCode(),
        type: 'discount',
        discount: 10,
        bonusDays: 0,
        maxActivations: 100,
        isActive: true,
        validUntil: '',
      });
    }
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setEditingPromocode(null);
  };

  const handleSubmit = () => {
    if (editingPromocode) {
      updateMutation.mutate({ id: editingPromocode.id, data: formData });
    } else {
      createMutation.mutate(formData);
    }
  };

  const handleToggle = (id: number) => {
    toggleMutation.mutate(id);
  };

  const handleDelete = (id: number) => {
    if (window.confirm('Вы уверены, что хотите удалить этот промокод?')) {
      deleteMutation.mutate(id);
    }
  };

  const generateRandomCode = () => {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    let code = '';
    for (let i = 0; i < 8; i++) {
      code += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return code;
  };

  const columns: GridColDef[] = [
    { field: 'id', headerName: 'ID', width: 70 },
    { field: 'code', headerName: 'Код', width: 150, renderCell: (params: GridRenderCellParams) => (
      <Typography variant="body2" fontFamily="monospace" fontWeight={600}>
        {params.value}
      </Typography>
    )},
    {
      field: 'type',
      headerName: 'Тип',
      width: 130,
      renderCell: (params: GridRenderCellParams) => {
        const type = PROMOCODE_TYPES.find(t => t.value === params.value);
        return <Chip label={type?.label || params.value} size="small" variant="outlined" />;
      },
    },
    {
      field: 'value',
      headerName: 'Значение',
      width: 120,
      renderCell: (params: GridRenderCellParams) => {
        const row = params.row as Promocode;
        if (row.type === 'discount') return `${row.discount}%`;
        if (row.type === 'bonus') return `${row.bonusDays} дн.`;
        if (row.type === 'trial') return `${row.bonusDays} дн.`;
        return '-';
      },
    },
    {
      field: 'activations',
      headerName: 'Активации',
      width: 120,
      renderCell: (params: GridRenderCellParams) => {
        const row = params.row as Promocode;
        return `${row.currentActivations} / ${row.maxActivations}`;
      },
    },
    {
      field: 'isActive',
      headerName: 'Статус',
      width: 110,
      renderCell: (params: GridRenderCellParams) => (
        <Chip
          label={params.value ? 'Активен' : 'Неактивен'}
          size="small"
          color={params.value ? 'success' : 'default'}
        />
      ),
    },
    {
      field: 'validUntil',
      headerName: 'Истекает',
      width: 120,
      renderCell: (params: GridRenderCellParams) =>
        params.value ? new Date(params.value).toLocaleDateString() : '—',
    },
    {
      field: 'actions',
      headerName: 'Действия',
      width: 150,
      sortable: false,
      renderCell: (params: GridRenderCellParams) => (
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <IconButton
            size="small"
            onClick={() => handleToggle(params.row.id)}
            title={params.row.isActive ? 'Деактивировать' : 'Активировать'}
          >
            <ToggleIcon fontSize="small" color={params.row.isActive ? 'success' : 'disabled'} />
          </IconButton>
          <IconButton
            size="small"
            onClick={() => handleOpenDialog(params.row as Promocode)}
            title="Редактировать"
          >
            <EditIcon fontSize="small" />
          </IconButton>
          <IconButton
            size="small"
            onClick={() => handleDelete(params.row.id)}
            title="Удалить"
            color="error"
          >
            <DeleteIcon fontSize="small" />
          </IconButton>
        </Box>
      ),
    },
  ];

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" fontWeight={600} gutterBottom>
            🎟 Промокоды
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Управление промокодами и скидками
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => handleOpenDialog()}
        >
          Создать промокод
        </Button>
      </Box>

      <Card>
        <DataGrid
          rows={data?.data || []}
          columns={columns}
          rowCount={data?.total || 0}
          loading={isLoading}
          pageSizeOptions={[10, 20, 50]}
          paginationModel={{ page, pageSize }}
          paginationMode="server"
          onPaginationModelChange={(m) => {
            setPage(m.page);
            setPageSize(m.pageSize);
          }}
          disableRowSelectionOnClick
          autoHeight
          sx={{ border: 'none' }}
        />
      </Card>

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onClose={handleCloseDialog} maxWidth="sm" fullWidth>
        <DialogTitle>
          {editingPromocode ? 'Редактировать промокод' : 'Создать промокод'}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
            <TextField
              label="Код промокода"
              value={formData.code}
              onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
              fullWidth
              inputProps={{ style: { fontFamily: 'monospace', fontWeight: 600 } }}
              helperText="Уникальный код для активации"
            />

            <Grid container spacing={2}>
              <Grid item xs={6}>
                <FormControl fullWidth>
                  <InputLabel>Тип промокода</InputLabel>
                  <Select
                    value={formData.type}
                    label="Тип промокода"
                    onChange={(e) => setFormData({ ...formData, type: e.target.value })}
                  >
                    {PROMOCODE_TYPES.map((type) => (
                      <MenuItem key={type.value} value={type.value}>
                        {type.label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={6}>
                {formData.type === 'discount' ? (
                  <TextField
                    label="Скидка (%)"
                    type="number"
                    value={formData.discount}
                    onChange={(e) => setFormData({ ...formData, discount: Number(e.target.value) })}
                    fullWidth
                    helperText="Процент скидки от 1 до 100"
                  />
                ) : (
                  <TextField
                    label="Бонусные дни"
                    type="number"
                    value={formData.bonusDays}
                    onChange={(e) => setFormData({ ...formData, bonusDays: Number(e.target.value) })}
                    fullWidth
                    helperText="Количество дней"
                  />
                )}
              </Grid>
            </Grid>

            <Grid container spacing={2}>
              <Grid item xs={6}>
                <TextField
                  label="Макс. активаций"
                  type="number"
                  value={formData.maxActivations}
                  onChange={(e) => setFormData({ ...formData, maxActivations: Number(e.target.value) })}
                  fullWidth
                  helperText="0 = безлимит"
                />
              </Grid>
              <Grid item xs={6}>
                <TextField
                  label="Дата истечения"
                  type="date"
                  value={formData.validUntil}
                  onChange={(e) => setFormData({ ...formData, validUntil: e.target.value })}
                  fullWidth
                  InputLabelProps={{ shrink: true }}
                  helperText="Оставьте пустым для бессрочного"
                />
              </Grid>
            </Grid>

            <FormControlLabel
              control={
                <Switch
                  checked={formData.isActive}
                  onChange={(e) => setFormData({ ...formData, isActive: e.target.checked })}
                />
              }
              label="Активен"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Отмена</Button>
          <Button
            onClick={handleSubmit}
            variant="contained"
            disabled={createMutation.isPending || updateMutation.isPending || !formData.code}
          >
            {createMutation.isPending || updateMutation.isPending
              ? 'Сохранение...'
              : editingPromocode
              ? 'Сохранить'
              : 'Создать'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}