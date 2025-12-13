import { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  Box,
  Drawer,
  AppBar,
  Toolbar,
  List,
  Typography,
  Divider,
  IconButton,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Avatar,
  Menu,
  MenuItem,
  useTheme,
  useMediaQuery,
  ListSubheader,
} from '@mui/material';
import {
  Menu as MenuIcon,
  Dashboard as DashboardIcon,
  People as PeopleIcon,
  Subscriptions as SubscriptionsIcon,
  Receipt as ReceiptIcon,
  LocalOffer as PromoIcon,
  Settings as SettingsIcon,
  Brightness4 as DarkModeIcon,
  Brightness7 as LightModeIcon,
  Logout as LogoutIcon,
  ViewList as PlansIcon,
  Campaign as BroadcastIcon,
  Payment as PaymentIcon,
  Backup as BackupIcon,
  AdminPanelSettings as AdminIcon,
  Image as ImageIcon,
  History as HistoryIcon,
  Lock as LockIcon,
  Waves as WavesIcon,
  Store as StoreIcon,
  FileUpload as ImportIcon,
  BarChart as StatsIcon,
} from '@mui/icons-material';
import { useAuthStore } from '../stores/authStore';
import { useThemeStore } from '../stores/themeStore';

const drawerWidth = 280;

const mainMenuItems = [
  { text: '🎛 Панель управления', icon: <DashboardIcon />, path: '/dashboard' },
  { text: '📊 Статистика', icon: <StatsIcon />, path: '/statistics' },
  { text: '👥 Пользователи', icon: <PeopleIcon />, path: '/users' },
  { text: '📨 Рассылка', icon: <BroadcastIcon />, path: '/broadcast' },
  { text: '🎟 Промокоды', icon: <PromoIcon />, path: '/promocodes' },
  { text: '🔐 Режим доступа', icon: <LockIcon />, path: '/access' },
];

const vpnMenuItems = [
  { text: '🌊 RemnaWave', icon: <WavesIcon />, path: '/remnawave' },
  { text: '🛒 RemnaShop', icon: <StoreIcon />, path: '/remnashop' },
];

const dataMenuItems = [
  { text: '📋 Планы', icon: <PlansIcon />, path: '/plans' },
  { text: '📦 Подписки', icon: <SubscriptionsIcon />, path: '/subscriptions' },
  { text: '💳 Транзакции', icon: <ReceiptIcon />, path: '/transactions' },
  { text: '💰 Платежные системы', icon: <PaymentIcon />, path: '/gateways' },
];

const systemMenuItems = [
  { text: '📥 Импорт пользователей', icon: <ImportIcon />, path: '/import' },
  { text: '👑 Администраторы', icon: <AdminIcon />, path: '/bot-admins' },
  { text: '🖼 Баннеры', icon: <ImageIcon />, path: '/banners' },
  { text: '📜 Журнал аудита', icon: <HistoryIcon />, path: '/audit' },
  { text: '💾 Бэкапы', icon: <BackupIcon />, path: '/backup' },
  { text: '⚙️ Настройки', icon: <SettingsIcon />, path: '/settings' },
];

export default function MainLayout() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [mobileOpen, setMobileOpen] = useState(false);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const { mode, toggleMode } = useThemeStore();

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  const handleMenuClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const renderMenuItems = (items: typeof mainMenuItems) => (
    items.map((item) => (
      <ListItemButton
        key={item.text}
        selected={location.pathname === item.path}
        onClick={() => {
          navigate(item.path);
          if (isMobile) setMobileOpen(false);
        }}
        sx={{ borderRadius: 1, mb: 0.5 }}
      >
        <ListItemIcon sx={{ minWidth: 40 }}>{item.icon}</ListItemIcon>
        <ListItemText primary={item.text} />
      </ListItemButton>
    ))
  );

  const drawer = (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Toolbar sx={{ px: 2 }}>
        <Typography variant="h6" noWrap component="div" sx={{ fontWeight: 700 }}>
          🛒 RemnaShop Admin
        </Typography>
      </Toolbar>
      <Divider />
      <List sx={{ flex: 1, px: 1, overflow: 'auto' }}>
        <ListSubheader sx={{ bgcolor: 'transparent', lineHeight: 2.5 }}>
          Основное
        </ListSubheader>
        {renderMenuItems(mainMenuItems)}
        
        <ListSubheader sx={{ bgcolor: 'transparent', lineHeight: 2.5, mt: 1 }}>
          VPN Панели
        </ListSubheader>
        {renderMenuItems(vpnMenuItems)}
        
        <ListSubheader sx={{ bgcolor: 'transparent', lineHeight: 2.5, mt: 1 }}>
          Данные
        </ListSubheader>
        {renderMenuItems(dataMenuItems)}
        
        <ListSubheader sx={{ bgcolor: 'transparent', lineHeight: 2.5, mt: 1 }}>
          Система
        </ListSubheader>
        {renderMenuItems(systemMenuItems)}
      </List>
      <Divider />
      <Box sx={{ p: 2 }}>
        <Typography variant="caption" color="text.secondary">
          Version 1.0.0
        </Typography>
      </Box>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <AppBar
        position="fixed"
        sx={{
          width: { md: `calc(100% - ${drawerWidth}px)` },
          ml: { md: `${drawerWidth}px` },
          bgcolor: 'background.paper',
          color: 'text.primary',
          boxShadow: 'none',
          borderBottom: 1,
          borderColor: 'divider',
        }}
      >
        <Toolbar>
          <IconButton
            color="inherit"
            edge="start"
            onClick={handleDrawerToggle}
            sx={{ mr: 2, display: { md: 'none' } }}
          >
            <MenuIcon />
          </IconButton>
          <Box sx={{ flexGrow: 1 }} />
          <IconButton onClick={toggleMode} color="inherit">
            {mode === 'dark' ? <LightModeIcon /> : <DarkModeIcon />}
          </IconButton>
          <IconButton onClick={handleMenuClick} sx={{ ml: 1 }}>
            <Avatar sx={{ width: 32, height: 32, bgcolor: 'primary.main' }}>
              {user?.username?.charAt(0).toUpperCase()}
            </Avatar>
          </IconButton>
          <Menu
            anchorEl={anchorEl}
            open={Boolean(anchorEl)}
            onClose={handleMenuClose}
            transformOrigin={{ horizontal: 'right', vertical: 'top' }}
            anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
          >
            <MenuItem disabled>
              <Typography variant="body2">{user?.username}</Typography>
            </MenuItem>
            <Divider />
            <MenuItem onClick={handleLogout}>
              <ListItemIcon>
                <LogoutIcon fontSize="small" />
              </ListItemIcon>
              Выйти
            </MenuItem>
          </Menu>
        </Toolbar>
      </AppBar>

      <Box
        component="nav"
        sx={{ width: { md: drawerWidth }, flexShrink: { md: 0 } }}
      >
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={handleDrawerToggle}
          ModalProps={{ keepMounted: true }}
          sx={{
            display: { xs: 'block', md: 'none' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: drawerWidth,
            },
          }}
        >
          {drawer}
        </Drawer>
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', md: 'block' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: drawerWidth,
            },
          }}
          open
        >
          {drawer}
        </Drawer>
      </Box>

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          width: { md: `calc(100% - ${drawerWidth}px)` },
          mt: '64px',
          bgcolor: 'background.default',
          minHeight: 'calc(100vh - 64px)',
        }}
      >
        <Outlet />
      </Box>
    </Box>
  );
}