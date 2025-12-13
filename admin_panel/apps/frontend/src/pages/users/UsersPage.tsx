import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Box,
  Typography,
  TextField,
  InputAdornment,
  Card,
  Chip,
  IconButton,
  Tooltip,
} from '@mui/material';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import {
  Search as SearchIcon,
  Visibility as ViewIcon,
  Block as BlockIcon,
  CheckCircle as UnblockIcon,
} from '@mui/icons-material';
import { api } from '../../api/client';

export default function UsersPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['users', page, pageSize, search],
    queryFn: async () => {
      const response = await api.get('/users', {
        params: { page: page + 1, limit: pageSize, search },
      });
      return response.data;
    },
  });

  const columns: GridColDef[] = [
    { field: 'id', headerName: 'ID', width: 70 },
    {
      field: 'telegramId',
      headerName: 'Telegram ID',
      width: 130,
    },
    {
      field: 'username',
      headerName: 'Username',
      width: 150,
      renderCell: (params: GridRenderCellParams) => (
        params.value ? `@${params.value}` : '-'
      ),
    },
    {
      field: 'name',
      headerName: 'Name',
      width: 150,
    },
    {
      field: 'role',
      headerName: 'Role',
      width: 100,
      renderCell: (params: GridRenderCellParams) => (
        <Chip
          label={params.value}
          size="small"
          color={params.value === 'admin' ? 'primary' : 'default'}
        />
      ),
    },
    {
      field: 'isBlocked',
      headerName: 'Status',
      width: 100,
      renderCell: (params: GridRenderCellParams) => (
        <Chip
          label={params.value ? 'Blocked' : 'Active'}
          size="small"
          color={params.value ? 'error' : 'success'}
        />
      ),
    },
    {
      field: 'points',
      headerName: 'Points',
      width: 80,
    },
    {
      field: 'createdAt',
      headerName: 'Registered',
      width: 120,
      renderCell: (params: GridRenderCellParams) => (
        new Date(params.value).toLocaleDateString()
      ),
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 120,
      sortable: false,
      renderCell: (params: GridRenderCellParams) => (
        <Box>
          <Tooltip title="View">
            <IconButton
              size="small"
              onClick={() => navigate(`/users/${params.row.id}`)}
            >
              <ViewIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title={params.row.isBlocked ? 'Unblock' : 'Block'}>
            <IconButton size="small" color={params.row.isBlocked ? 'success' : 'error'}>
              {params.row.isBlocked ? <UnblockIcon fontSize="small" /> : <BlockIcon fontSize="small" />}
            </IconButton>
          </Tooltip>
        </Box>
      ),
    },
  ];

  return (
    <Box>
      <Typography variant="h4" fontWeight={600} gutterBottom>
        Users
      </Typography>
      <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
        Manage bot users
      </Typography>

      <Card sx={{ mb: 3, p: 2 }}>
        <TextField
          fullWidth
          placeholder="Search by Telegram ID, username, or name..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon />
              </InputAdornment>
            ),
          }}
        />
      </Card>

      <Card>
        <DataGrid
          rows={data?.data || []}
          columns={columns}
          rowCount={data?.total || 0}
          loading={isLoading}
          pageSizeOptions={[10, 20, 50]}
          paginationModel={{ page, pageSize }}
          paginationMode="server"
          onPaginationModelChange={(model) => {
            setPage(model.page);
            setPageSize(model.pageSize);
          }}
          disableRowSelectionOnClick
          autoHeight
          sx={{ border: 'none' }}
        />
      </Card>
    </Box>
  );
}