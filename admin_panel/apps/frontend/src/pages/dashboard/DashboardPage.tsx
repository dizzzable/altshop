import { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Grid,
  Typography,
  Paper,
  CircularProgress,
  LinearProgress,
  alpha,
} from '@mui/material';
import {
  Memory as MemoryIcon,
  Storage as StorageIcon,
  Speed as SpeedIcon,
  Timer as TimerIcon,
} from '@mui/icons-material';
import api from '../../api/client';

interface CpuMetrics {
  usage: number;
  cores: number;
  model: string;
  speed: number;
}

interface MemoryMetrics {
  total: number;
  used: number;
  free: number;
  usagePercent: number;
}

interface DiskMetrics {
  total: number;
  used: number;
  free: number;
  usagePercent: number;
}

interface SystemMetrics {
  cpu: CpuMetrics;
  memory: MemoryMetrics;
  disk: DiskMetrics;
  uptime: number;
  platform: string;
  hostname: string;
  timestamp: string;
}

const formatBytes = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
};

const formatUptime = (seconds: number): string => {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  
  if (days > 0) return `${days}д ${hours}ч`;
  if (hours > 0) return `${hours}ч ${minutes}м`;
  return `${minutes}м`;
};

const getProgressColor = (percent: number): string => {
  if (percent < 60) return '#10b981';
  if (percent < 85) return '#f59e0b';
  return '#ef4444';
};

interface MetricCardProps {
  title: string;
  value: string;
  subtitle?: string;
  percent: number;
  icon: React.ReactNode;
}

function MetricCard({ title, value, subtitle, percent, icon }: MetricCardProps) {
  const color = getProgressColor(percent);
  
  return (
    <Paper sx={{ p: 2.5, height: '100%' }}>
      <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="body2" color="text.secondary" fontWeight={500}>
          {title}
        </Typography>
        <Box
          sx={{
            width: 40,
            height: 40,
            borderRadius: '12px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: `linear-gradient(135deg, ${alpha(color, 0.2)} 0%, ${alpha(color, 0.1)} 100%)`,
            border: `1px solid ${alpha(color, 0.2)}`,
            color: color,
          }}
        >
          {icon}
        </Box>
      </Box>
      
      <Typography 
        variant="h4" 
        fontWeight={700} 
        sx={{ fontFamily: '"JetBrains Mono", monospace', mb: 0.5 }}
      >
        {value}
      </Typography>
      
      {subtitle && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
          {subtitle}
        </Typography>
      )}
      
      <Box sx={{ mt: 'auto' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
          <Typography variant="caption" color="text.secondary">
            Использовано
          </Typography>
          <Typography variant="caption" fontWeight={600} sx={{ color }}>
            {percent.toFixed(1)}%
          </Typography>
        </Box>
        <LinearProgress
          variant="determinate"
          value={percent}
          sx={{
            height: 6,
            borderRadius: 3,
            bgcolor: alpha(color, 0.1),
            '& .MuiLinearProgress-bar': {
              bgcolor: color,
              borderRadius: 3,
            },
          }}
        />
      </Box>
    </Paper>
  );
}

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMetrics = useCallback(async () => {
    try {
      const response = await api.get<SystemMetrics>('/dashboard/system-metrics');
      setMetrics(response.data);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch system metrics:', err);
      setError('Не удалось загрузить метрики сервера');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 5000);
    return () => clearInterval(interval);
  }, [fetchMetrics]);

  // Mock data for dev mode
  const isDev = import.meta.env.DEV;
  const mockMetrics: SystemMetrics = {
    cpu: { usage: 12.5, cores: 4, model: 'Intel Xeon E5-2680 v4', speed: 2400 },
    memory: { total: 8589934592, used: 5368709120, free: 3221225472, usagePercent: 62.5 },
    disk: { total: 107374182400, used: 53687091200, free: 53687091200, usagePercent: 50 },
    uptime: 864000,
    platform: 'linux',
    hostname: 'server-prod',
    timestamp: new Date().toISOString(),
  };

  const displayMetrics = isDev && !metrics ? mockMetrics : metrics;

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" fontWeight={700} gutterBottom>
          Панель управления
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Мониторинг состояния сервера
        </Typography>
      </Box>

      {/* Server Info */}
      {displayMetrics && (
        <Paper sx={{ p: 2, mb: 3, display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
          <Box>
            <Typography variant="caption" color="text.secondary">Хост</Typography>
            <Typography variant="body2" fontWeight={600}>{displayMetrics.hostname}</Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">Платформа</Typography>
            <Typography variant="body2" fontWeight={600}>{displayMetrics.platform}</Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">Uptime</Typography>
            <Typography variant="body2" fontWeight={600}>{formatUptime(displayMetrics.uptime)}</Typography>
          </Box>
          <Box sx={{ ml: 'auto', display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box
              sx={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                bgcolor: '#10b981',
                animation: 'pulse 2s infinite',
                '@keyframes pulse': {
                  '0%, 100%': { opacity: 1 },
                  '50%': { opacity: 0.4 },
                },
              }}
            />
            <Typography variant="caption" color="text.secondary">
              Обновление: 5 сек
            </Typography>
          </Box>
        </Paper>
      )}

      {/* Metrics */}
      {isLoading && !displayMetrics ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress sx={{ color: '#10b981' }} size={48} />
        </Box>
      ) : error && !isDev ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="h6" color="error" gutterBottom>
            ⚠️ Ошибка загрузки
          </Typography>
          <Typography color="text.secondary">{error}</Typography>
        </Paper>
      ) : displayMetrics ? (
        <Grid container spacing={2}>
          <Grid item xs={12} md={4}>
            <MetricCard
              title="Процессор (CPU)"
              value={`${displayMetrics.cpu.usage}%`}
              subtitle={`${displayMetrics.cpu.cores} ядер • ${displayMetrics.cpu.speed} MHz`}
              percent={displayMetrics.cpu.usage}
              icon={<SpeedIcon sx={{ fontSize: 20 }} />}
            />
          </Grid>
          <Grid item xs={12} md={4}>
            <MetricCard
              title="Оперативная память"
              value={formatBytes(displayMetrics.memory.used)}
              subtitle={`из ${formatBytes(displayMetrics.memory.total)}`}
              percent={displayMetrics.memory.usagePercent}
              icon={<MemoryIcon sx={{ fontSize: 20 }} />}
            />
          </Grid>
          <Grid item xs={12} md={4}>
            <MetricCard
              title="Диск"
              value={formatBytes(displayMetrics.disk.used)}
              subtitle={`из ${formatBytes(displayMetrics.disk.total)}`}
              percent={displayMetrics.disk.usagePercent}
              icon={<StorageIcon sx={{ fontSize: 20 }} />}
            />
          </Grid>
        </Grid>
      ) : null}
    </Box>
  );
}
