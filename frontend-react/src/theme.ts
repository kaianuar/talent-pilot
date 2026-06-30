import { createTheme, responsiveFontSizes } from '@mui/material/styles';

// Modern earthy palette
const palette = {
  cream: '#EDEEC0',        // page background
  darkKhaki: '#433E0E',    // text, headers, primary
  dustyOlive: '#7C9082',   // primary accent, buttons
  drySage: '#A7A284',      // secondary, borders, muted text
  lightSage: '#D0C88E',    // hover states, subtle highlights
  white: '#FFFFFF',        // card backgrounds
  nearBlack: '#1A1A1A',    // high contrast text
};

let theme = createTheme({
  palette: {
    primary: {
      main: palette.dustyOlive,
      light: palette.drySage,
      dark: '#5A7060',
      contrastText: '#FFFFFF',
    },
    secondary: {
      main: palette.drySage,
      light: palette.lightSage,
      dark: '#8A8264',
      contrastText: palette.nearBlack,
    },
    background: {
      default: palette.cream,
      paper: palette.white,
    },
    text: {
      primary: palette.nearBlack,
      secondary: palette.dustyOlive,
    },
    divider: palette.drySage,
  },
  typography: {
    fontFamily: '"Inter", "system-ui", "-apple-system", sans-serif',
    h1: { fontWeight: 700, letterSpacing: '-0.02em' },
    h2: { fontWeight: 600, letterSpacing: '-0.01em' },
    h3: { fontWeight: 600 },
    h4: { fontWeight: 600 },
    h5: { fontWeight: 600, fontSize: '1.1rem' },
    h6: { fontWeight: 600, fontSize: '1rem' },
    button: { textTransform: 'none', fontWeight: 500 },
    body1: { lineHeight: 1.6 },
    body2: { lineHeight: 1.5 },
  },
  shape: { borderRadius: 12 },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          padding: '8px 20px',
          transition: 'all 0.2s ease',
        },
        contained: {
          boxShadow: 'none',
          '&:hover': { boxShadow: '0 2px 8px rgba(124,144,130,0.3)' },
        },
        outlined: {
          borderColor: palette.dustyOlive,
          '&:hover': { bgcolor: `${palette.dustyOlive}10` },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          backgroundImage: 'none',
        },
        elevation1: {
          boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          bgcolor: palette.white,
          color: palette.nearBlack,
          boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: { borderRadius: 8 },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: 8,
            bgcolor: palette.white,
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
        },
      },
    },
  },
});

theme = responsiveFontSizes(theme);

export default theme;
