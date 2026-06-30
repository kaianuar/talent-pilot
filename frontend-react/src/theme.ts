import { createTheme, responsiveFontSizes } from '@mui/material/styles';

// Earthy color palette
const palette = {
  cream: '#EDEEC0',
  darkKhaki: '#433E0E',
  dustyOlive: '#7C9082',
  drySage: '#A7A284',
  lightSage: '#D0C88E',
  white: '#FFFFFF',
};

let theme = createTheme({
  palette: {
    primary: {
      main: palette.dustyOlive,
      light: palette.drySage,
      dark: '#5A7060',
      contrastText: palette.white,
    },
    secondary: {
      main: palette.drySage,
      light: palette.lightSage,
      dark: '#8A8264',
      contrastText: palette.darkKhaki,
    },
    background: {
      default: palette.cream,
      paper: palette.lightSage,
    },
    text: {
      primary: palette.darkKhaki,
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
