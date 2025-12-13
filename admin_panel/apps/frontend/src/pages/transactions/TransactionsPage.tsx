import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Box, Typography, Card, Chip } from '@mui/material';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import { api } from '../../api/client';

export default function TransactionsPage() {
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);

  const { data, isLoading } = useQuery({
    queryKey: ['transactions', page, pageSize],
    queryFn: async () => {
      const response = await api.get('/transactions', { params: { page: page + 1, limit: pageSize } });
      return response.data;
    },
  });

  const columns: GridColDef[] = [
    { field: 'id', headerName: 'ID', width: 70 },
    { field: 'userTelegramId', headerName: 'User', width: 130 },
    { field: 'amount', headerName: 'Amount', width: 100 },
    { field: 'currency', headerName: 'Currency', width: 80 },
    {
      field: 'status', headerName: 'Status', width: 100,
      renderCell: (params: GridRenderCellParams) => (
        <Chip label={params.value} size="small" color={params.value === 'completed' ? 'success' : params.value === 'pending' ? 'warning' : 'error'} />
      ),
    },
    { field: 'type', headerName: 'Type', width: 100 },
    { field: 'paymentGateway', headerName: 'Gateway', width: 120 },
    { field: 'createdAt', headerName: 'Date', width: 120, renderCell: (params: GridRenderCellParams) => new Date(params.value).toLocaleDateString() },
  ];

  return (
    <Box>
      <Typography variant="h4" fontWeight={600} gutterBottom>Transactions</Typography>
      <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>View payment transactions</Typography>
      <Card>
        <DataGrid rows={data?.data || []} columns={columns} rowCount={data?.total || 0} loading={isLoading}
          pageSizeOptions={[10, 20, 50]} paginationModel={{ page, pageSize }} paginationMode="server"
          onPaginationModelChange={(m) => { setPage(m.page); setPageSize(m.pageSize); }}
          disableRowSelectionOnClick autoHeight sx={{ border: 'none' }} />
      </Card>
    </Box>
  );
}