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
  alpha,
} from '@mui/material';
import {
  Menu as MenuIcon,
  GridView as DashboardIcon,
  PeopleOutline as PeopleIcon,
  Inventory2Outlined as SubscriptionsIcon,
  ReceiptLongOutlined as ReceiptIcon,
  ConfirmationNumberOutlined as PromoIcon,
  SettingsOutlined as SettingsIcon,
  DarkModeOutlined as DarkModeIcon,
  LightModeOutlined as LightModeIcon,
  LogoutOutlined as LogoutIcon,
  ListAltOutlined as PlansIcon,
  CampaignOutlined as BroadcastIcon,
  AccountBalanceWalletOutlined as PaymentIcon,
  CloudDownloadOutlined as BackupIcon,
  SupervisorAccountOutlined as AdminIcon,
  ImageOutlined as ImageIcon,
  HistoryOutlined as HistoryIcon,
  LockOutlined as LockIcon,
  WavesOutlined as WavesIcon,
  StorefrontOutlined as StoreIcon,
  FileUploadOutlined as ImportIcon,
  InsightsOutlined as StatsIcon,
  KeyboardArrowRight as ArrowIcon,
} from '@mui/icons-material';
import { useAuthStore } from '../stores/authStore';
import { useThemeStore } from '../stores/themeStore';

const drawerWidth = 260;

interface MenuItemType {
  text: string;
  icon: React.ReactNode;
  path: string;
}

interface MenuSection {
  title: string;
  items: MenuItemType[];
}

const menuSections: MenuSection[] = [
  {
    title: 'ОБЗОР',
    items: [
      { text: 'Главная', icon: <DashboardIcon />, path: '/dashboard' },
    ],
  },
  {
    title: 'УПРАВЛЕНИЕ',
    items: [
      { text: 'Пользователи', icon: <PeopleIcon />, path: '/users' },
      { text: 'Статистика', icon: <StatsIcon />, path: '/statistics' },
      { text: 'Рассылка', icon: <BroadcastIcon />, path: '/broadcast' },
      { text: 'Промокоды', icon: <PromoIcon />, path: '/promocodes' },
      { text: 'Режим доступа', icon: <LockIcon />, path: '/access' },
    ],
  },
  {
    title: 'VPN ПАНЕЛИ',
    items: [
      { text: 'RemnaWave', icon: <WavesIcon />, path: '/remnawave' },
      { text: 'RemnaShop', icon: <StoreIcon />, path: '/remnashop' },
    ],
  },
  {
    title: 'ДАННЫЕ',
    items: [
      { text: 'Планы', icon: <PlansIcon />, path: '/plans' },
      { text: 'Подписки', icon: <SubscriptionsIcon />, path: '/subscriptions' },
      { text: 'Транзакции', icon: <ReceiptIcon />, path: '/transactions' },
      { text: 'Платежные системы', icon: <PaymentIcon />, path: '/gateways' },
    ],
  },
  {
    title: 'СИСТЕМА',
    items: [
      { text: 'Импорт', icon: <ImportIcon />, path: '/import' },
      { text: 'Администраторы', icon: <AdminIcon />, path: '/bot-admins' },
      { text: 'Баннеры', icon: <ImageIcon />, path: '/banners' },
      { text: 'Журнал аудита', icon: <HistoryIcon />, path: '/audit' },
      { text: 'Бэкапы', icon: <BackupIcon />, path: '/backup' },
      { text: 'Настройки', icon: <SettingsIcon />, path: '/settings' },
    ],
  },
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

  const drawer = (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Logo */}
      <Box sx={{ p: 2.5, display: 'flex', alignItems: 'center', gap: 1.5 }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 0.5,
          }}
        >
          {[1, 2, 3, 4].map((i) => (
            <Box
              key={i}
              sx={{
                width: 4,
                height: i === 1 ? 16 : i === 2 ? 24 : i === 3 ? 20 : 12,
                borderRadius: 1,
                bgcolor: '#10b981',
              }}
            />
          ))}
        </Box>
        <Typography 
          variant="h6" 
          sx={{ 
            fontWeight: 700,
            letterSpacing: '-0.02em',
          }}
        >
          Halifolium
        </Typography>
      </Box>

      {/* Menu */}
      <Box sx={{ flex: 1, overflow: 'auto', px: 1.5 }}>
        {menuSections.map((section, sectionIndex) => (
          <Box key={section.title} sx={{ mb: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 1, py: 1.5 }}>
              <Box
                sx={{
                  width: 3,
                  height: 3,
                  borderRadius: '50%',
                  bgcolor: 'text.secondary',
                  opacity: 0.5,
                }}
              />
              <Typography
                variant="caption"
                sx={{
                  color: 'text.secondary',
                  fontWeight: 600,
                  letterSpacing: '0.08em',
                  fontSize: '0.7rem',
                }}
              >
                {section.title}
              </Typography>
            </Box>
            <List disablePadding>
              {section.items.map((item) => {
                const isSelected = location.pathname === item.path;
                return (
                  <ListItemButton
                    key={item.path}
                    selected={isSelected}
                    onClick={() => {
                      navigate(item.path);
                      if (isMobile) setMobileOpen(false);
                    }}
                    sx={{
                      py: 1,
                      px: 1.5,
                      mb: 0.25,
                      borderRadius: 1.5,
                      transition: 'all 0.15s ease',
                      '&.Mui-selected': {
                        bgcolor: alpha('#10b981', 0.12),
                        '&::before': {
                          content: '""',
                          position: 'absolute',
                          left: 0,
                          top: '50%',
                          transform: 'translateY(-50%)',
                          width: 3,
                          height: 20,
                          borderRadius: 1,
                          bgcolor: '#10b981',
                        },
                      },
                    }}
                  >
                    <ListItemIcon 
                      sx={{ 
                        minWidth: 36,
                        color: isSelected ? '#10b981' : 'text.secondary',
                      }}
                    >
                      {item.icon}
                    </ListItemIcon>
                    <ListItemText 
                      primary={item.text}
                      primaryTypographyProps={{
                        fontSize: '0.875rem',
                        fontWeight: isSelected ? 600 : 400,
                      }}
                    />
                    {isSelected && (
                      <ArrowIcon sx={{ fontSize: 18, color: '#10b981' }} />
                    )}
                  </ListItemButton>
                );
              })}
            </List>
            {sectionIndex < menuSections.length - 1 && (
              <Divider sx={{ my: 1, mx: 1, borderStyle: 'dashed' }} />
            )}
          </Box>
        ))}
      </Box>

      {/* Footer */}
      <Divider />
      <Box sx={{ p: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="caption" color="text.secondary">
          v1.0.0
        </Typography>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 0.5,
            px: 1,
            py: 0.5,
            borderRadius: 1,
            bgcolor: alpha('#10b981', 0.1),
          }}
        >
          <Box
            sx={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              bgcolor: '#10b981',
              animation: 'pulse 2s infinite',
              '@keyframes pulse': {
                '0%, 100%': { opacity: 1 },
                '50%': { opacity: 0.4 },
              },
            }}
          />
          <Typography variant="caption" sx={{ color: '#10b981', fontWeight: 500 }}>
            Online
          </Typography>
        </Box>
      </Box>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <AppBar
        position="fixed"
        elevation={0}
        sx={{
          width: { md: `calc(100% - ${drawerWidth}px)` },
          ml: { md: `${drawerWidth}px` },
          bgcolor: 'background.default',
          color: 'text.primary',
          borderBottom: '1px solid',
          borderColor: 'divider',
        }}
      >
        <Toolbar sx={{ gap: 1 }}>
          <IconButton
            color="inherit"
            edge="start"
            onClick={handleDrawerToggle}
            sx={{ display: { md: 'none' } }}
          >
            <MenuIcon />
          </IconButton>
          <Box sx={{ flexGrow: 1 }} />
          
          <IconButton 
            onClick={toggleMode} 
            size="small"
            sx={{
              bgcolor: alpha(theme.palette.text.primary, 0.05),
              '&:hover': {
                bgcolor: alpha(theme.palette.text.primary, 0.1),
              },
            }}
          >
            {mode === 'dark' ? <LightModeIcon fontSize="small" /> : <DarkModeIcon fontSize="small" />}
          </IconButton>
          
          <IconButton onClick={handleMenuClick} size="small">
            <Avatar 
              sx={{ 
                width: 32, 
                height: 32, 
                bgcolor: '#10b981',
                fontSize: '0.875rem',
                fontWeight: 600,
              }}
            >
              {user?.username?.charAt(0).toUpperCase()}
            </Avatar>
          </IconButton>
          
          <Menu
            anchorEl={anchorEl}
            open={Boolean(anchorEl)}
            onClose={handleMenuClose}
            transformOrigin={{ horizontal: 'right', vertical: 'top' }}
            anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
            PaperProps={{
              sx: {
                mt: 1,
                minWidth: 180,
              },
            }}
          >
            <Box sx={{ px: 2, py: 1.5 }}>
              <Typography variant="body2" fontWeight={600}>
                {user?.username}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {user?.role}
              </Typography>
            </Box>
            <Divider />
            <MenuItem onClick={handleLogout} sx={{ py: 1.5 }}>
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
              bgcolor: 'background.default',
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
              bgcolor: 'background.default',
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
