import { createTheme, responsiveFontSizes } from '@mui/material/styles';

// Blue color palette
const palette = {
  lightBlue: '#a3c7e0',    // backgrounds, subtle highlights
  viking: '#73b0d9',       // secondary accents, borders
  bostonBlue: '#4a8fc4',   // primary actions, buttons
  jellyBean: '#2b699c',    // primary dark, hover states
  blumine: '#1f507a',      // text, headers, dark accents
  white: '#FFFFFF',
  nearBlack: '#1A1A1A',
};

let theme = createTheme({
  palette: {
    primary: {
      main: palette.bostonBlue,
      light: palette.viking,
      dark: palette.jellyBean,
      contrastText: palette.white,
    },
    secondary: {
      main: palette.viking,
      light: palette.lightBlue,
      dark: palette.bostonBlue,
      contrastText: palette.white,
    },
    background: {
      default: palette.lightBlue,
      paper: palette.white,
    },
    text: {
      primary: palette.blumine,
      secondary: palette.jellyBean,
    },
    divider: palette.viking,
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
        },
        contained: {
          boxShadow: 'none',
          '&:hover': { boxShadow: '0 2px 8px rgba(74,143,196,0.3)' },
        },
        outlined: {
          borderColor: palette.bostonBlue,
          '&:hover': { bgcolor: `${palette.bostonBlue}10` },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          backgroundImage: 'none',
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
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 12,
        },
      },
    },
  },
});

theme = responsiveFontSizes(theme);

export default theme;
