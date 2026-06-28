import { createTheme, responsiveFontSizes } from '@mui/material/styles';

// TalentPilot Brand Colors
const brandColors = {
  primary: {
    main: '#2563eb', // Blue 600
    light: '#3b82f6',
    dark: '#1d4ed8',
    contrastText: '#ffffff',
  },
  secondary: {
    main: '#7c3aed', // Violet 600
    light: '#8b5cf6',
    dark: '#6d28d9',
    contrastText: '#ffffff',
  },
  success: {
    main: '#10b981', // Emerald 500
    light: '#34d399',
    dark: '#059669',
  },
  warning: {
    main: '#f59e0b', // Amber 500
    light: '#fbbf24',
    dark: '#d97706',
  },
  error: {
    main: '#ef4444', // Red 500
    light: '#f87171',
    dark: '#dc2626',
  },
  background: {
    default: '#f8fafc', // Slate 50
    paper: '#ffffff',
  },
  text: {
    primary: '#1e293b', // Slate 800
    secondary: '#64748b', // Slate 500
  },
};

let theme = createTheme({
  palette: brandColors,
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    h1: {
      fontWeight: 700,
    },
    h2: {
      fontWeight: 600,
    },
    h3: {
      fontWeight: 600,
    },
    h4: {
      fontWeight: 600,
    },
    h5: {
      fontWeight: 600,
    },
    h6: {
      fontWeight: 600,
    },
    button: {
      textTransform: 'none',
      fontWeight: 600,
    },
  },
  shape: {
    borderRadius: 8,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          borderRadius: 12,
        },
      },
    },
  },
});

// Make fonts responsive
theme = responsiveFontSizes(theme);

export default theme;
