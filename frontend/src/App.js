import React, { useState, useEffect, useRef } from 'react';
import { 
  ThemeProvider, 
  createTheme,
  CssBaseline,
  Box,
  Paper,
  TextField,
  IconButton,
  Typography,
  CircularProgress,
  Snackbar,
  Alert,
  AppBar,
  Toolbar,
  Badge,
  Avatar,
  Divider,
  Tooltip,
  Fade,
  Switch,
  FormControlLabel,
  useMediaQuery
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import WifiIcon from '@mui/icons-material/Wifi';
import WifiOffIcon from '@mui/icons-material/WifiOff';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import PersonIcon from '@mui/icons-material/Person';
import Brightness4Icon from '@mui/icons-material/Brightness4';
import Brightness7Icon from '@mui/icons-material/Brightness7';
import { styled } from '@mui/material/styles';

// Custom theme with light and dark color palettes
const getTheme = (mode) => createTheme({
  palette: {
    mode,
    primary: {
      main: '#FFB347', // Light orange
      light: '#FFC988',
      dark: '#E69A2E',
    },
    secondary: {
      main: '#555555', // Dark gray
      light: '#777777',
      dark: '#333333',
    },
    background: {
      default: mode === 'light' ? '#FFFFFF' : '#1E1E1E',
      paper: mode === 'light' ? '#F5F5F5' : '#2D2D2D',
    },
    text: {
      primary: mode === 'light' ? '#333333' : '#FFFFFF',
      secondary: mode === 'light' ? '#666666' : '#CCCCCC',
    },
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
    h5: {
      fontWeight: 500,
    },
  },
  components: {
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
        },
      },
    },
    MuiSwitch: {
      styleOverrides: {
        switchBase: {
          color: mode === 'light' ? '#FFB347' : '#FFFFFF',
        },
        track: {
          backgroundColor: mode === 'light' ? '#FFC988' : '#555555',
        },
      },
    },
  },
});

// Styled components
const AppContainer = styled(Box)(({ theme }) => ({
  height: '100vh',
  display: 'flex',
  flexDirection: 'column',
  backgroundColor: theme.palette.background.default,
}));

const ChatContainer = styled(Paper)(({ theme }) => ({
  flexGrow: 1,
  display: 'flex',
  flexDirection: 'column',
  margin: theme.spacing(2),
  marginTop: theme.spacing(1),
  marginBottom: theme.spacing(1),
  backgroundColor: theme.palette.background.paper,
  borderRadius: theme.spacing(2),
  overflow: 'hidden',
  boxShadow: '0 4px 20px rgba(0, 0, 0, 0.1)',
}));

const MessagesContainer = styled(Box)(({ theme }) => ({
  flexGrow: 1,
  overflowY: 'auto',
  padding: theme.spacing(2),
  display: 'flex',
  flexDirection: 'column',
  '&::-webkit-scrollbar': {
    width: '8px',
  },
  '&::-webkit-scrollbar-track': {
    background: theme.palette.background.default,
  },
  '&::-webkit-scrollbar-thumb': {
    background: theme.palette.mode === 'light' ? '#FFC988' : '#555555',
    borderRadius: '4px',
  },
}));

const MessageBubble = styled(Box)(({ theme, isUser }) => ({
  maxWidth: '70%',
  padding: theme.spacing(1.5),
  borderRadius: theme.spacing(2),
  marginBottom: theme.spacing(1),
  backgroundColor: isUser 
    ? (theme.palette.mode === 'light' ? '#F0F0F0' : '#555555')
    : (theme.palette.mode === 'light' ? '#FFB347' : '#333333'),
  color: isUser 
    ? (theme.palette.mode === 'light' ? '#333333' : '#FFFFFF')
    : '#FFFFFF',
  alignSelf: isUser ? 'flex-end' : 'flex-start',
  boxShadow: '0 2px 5px rgba(0,0,0,0.1)',
  position: 'relative',
  '&::before': {
    content: '""',
    position: 'absolute',
    width: 0,
    height: 0,
    top: '50%',
    border: '8px solid transparent',
    ...(isUser ? {
      right: '100%',
      borderRightColor: theme.palette.mode === 'light' ? '#F0F0F0' : '#555555',
      transform: 'translateY(-50%)',
    } : {
      left: '100%',
      borderLeftColor: theme.palette.mode === 'light' ? '#FFB347' : '#333333',
      transform: 'translateY(-50%)',
    }),
  },
}));

const InputContainer = styled(Box)(({ theme }) => ({
  display: 'flex',
  gap: theme.spacing(1),
  padding: theme.spacing(2),
  backgroundColor: theme.palette.background.paper,
  borderTop: `1px solid ${theme.palette.divider}`,
}));

const Logo = styled('div')(({ theme }) => ({
  display: 'flex',
  alignItems: 'center',
  gap: theme.spacing(1),
  '& svg': {
    fontSize: '2rem',
    color: theme.palette.mode === 'light' ? '#FFB347' : '#FFFFFF',
  },
}));

const StatusIndicator = styled(Badge)(({ theme }) => ({
  '& .MuiBadge-badge': {
    backgroundColor: theme.palette.success.main,
    color: theme.palette.success.main,
    boxShadow: `0 0 0 2px ${theme.palette.background.paper}`,
    '&::after': {
      position: 'absolute',
      top: 0,
      left: 0,
      width: '100%',
      height: '100%',
      borderRadius: '50%',
      animation: 'ripple 1.2s infinite ease-in-out',
      border: '1px solid currentColor',
      content: '""',
    },
  },
  '@keyframes ripple': {
    '0%': {
      transform: 'scale(.8)',
      opacity: 1,
    },
    '100%': {
      transform: 'scale(2.4)',
      opacity: 0,
    },
  },
}));

const TypingIndicator = styled(Box)(({ theme }) => ({
  display: 'flex',
  alignItems: 'center',
  gap: theme.spacing(0.5),
  padding: theme.spacing(1),
  backgroundColor: theme.palette.mode === 'light' ? '#F0F0F0' : '#555555',
  borderRadius: theme.spacing(2),
  width: 'fit-content',
  marginBottom: theme.spacing(1),
  alignSelf: 'flex-start',
  '& .dot': {
    width: 8,
    height: 8,
    borderRadius: '50%',
    backgroundColor: theme.palette.mode === 'light' ? '#FFB347' : '#FFFFFF',
    animation: 'bounce 1.4s infinite ease-in-out',
    '&:nth-of-type(1)': {
      animationDelay: '0s',
    },
    '&:nth-of-type(2)': {
      animationDelay: '0.2s',
    },
    '&:nth-of-type(3)': {
      animationDelay: '0.4s',
    },
  },
  '@keyframes bounce': {
    '0%, 80%, 100%': {
      transform: 'scale(0)',
    },
    '40%': {
      transform: 'scale(1)',
    },
  },
}));

const ThemeToggle = styled(Box)(({ theme }) => ({
  display: 'flex',
  alignItems: 'center',
  gap: theme.spacing(1),
  '& .MuiSwitch-root': {
    marginLeft: theme.spacing(1),
  },
}));

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [streamingMessage, setStreamingMessage] = useState('');
  const [darkMode, setDarkMode] = useState(false);
  const wsRef = useRef(null);
  const messagesEndRef = useRef(null);
  const streamingTimeoutRef = useRef(null);
  const prefersDarkMode = useMediaQuery('(prefers-color-scheme: dark)');

  // Initialize theme based on system preference
  useEffect(() => {
    setDarkMode(prefersDarkMode);
  }, [prefersDarkMode]);

  const theme = React.useMemo(() => getTheme(darkMode ? 'dark' : 'light'), [darkMode]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingMessage]);

  useEffect(() => {
    const connectWebSocket = () => {
      const ws = new WebSocket('ws://localhost:8000/ws');
      
      ws.onopen = () => {
        setIsConnected(true);
        console.log('Connected to WebSocket');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.error) {
            setError(data.error);
            setIsLoading(false);
            setStreamingMessage('');
          } else if (data.message) {
            if (data.is_chunk) {
              // Handle streaming chunks character by character
              const newChar = data.message;
              setStreamingMessage(prev => {
                const updated = prev + newChar;
                // Clear any existing timeout
                if (streamingTimeoutRef.current) {
                  clearTimeout(streamingTimeoutRef.current);
                }
                // Set a timeout to finalize the message if no new chunks arrive
                streamingTimeoutRef.current = setTimeout(() => {
                  if (updated === streamingMessage) {
                    setMessages(prev => [...prev, { text: updated, isUser: false }]);
                    setStreamingMessage('');
                    setIsLoading(false);
                  }
                }, 1000); // Wait 1 second of no new chunks before finalizing
                return updated;
              });
            } else {
              // Final message received
              setMessages(prev => [...prev, { text: data.message, isUser: false }]);
              setStreamingMessage('');
              setIsLoading(false);
            }
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
          setError('Error parsing server response');
          setIsLoading(false);
          setStreamingMessage('');
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        console.log('Disconnected from WebSocket');
        // Attempt to reconnect after 5 seconds
        setTimeout(connectWebSocket, 5000);
      };

      wsRef.current = ws;
    };

    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (streamingTimeoutRef.current) {
        clearTimeout(streamingTimeoutRef.current);
      }
    };
  }, []);

  const handleSend = () => {
    if (!input.trim() || !isConnected) return;

    const message = input.trim();
    setMessages(prev => [...prev, { text: message, isUser: true }]);
    setInput('');
    setIsLoading(true);
    setStreamingMessage('');

    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({ message }));
    }
  };

  const handleKeyPress = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  const handleCloseError = () => {
    setError(null);
  };

  const toggleTheme = () => {
    setDarkMode(!darkMode);
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AppContainer>
        <AppBar position="static" color="transparent" elevation={0}>
          <Toolbar>
            <Logo>
              <SmartToyIcon />
              <Typography variant="h5" component="div" sx={{ flexGrow: 1 }}>
                Obsrv AI
              </Typography>
            </Logo>
            <Box sx={{ flexGrow: 1 }} />
            <ThemeToggle>
              <Tooltip title={darkMode ? "Switch to Light Mode" : "Switch to Dark Mode"}>
                <IconButton onClick={toggleTheme} color="inherit">
                  {darkMode ? <Brightness7Icon /> : <Brightness4Icon />}
                </IconButton>
              </Tooltip>
              <FormControlLabel
                control={
                  <Switch 
                    checked={darkMode} 
                    onChange={toggleTheme}
                    color="primary"
                  />
                }
                label={darkMode ? "Dark Mode" : "Light Mode"}
              />
            </ThemeToggle>
            <Tooltip title={isConnected ? "Connected" : "Disconnected"}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, ml: 2 }}>
                {isConnected ? (
                  <StatusIndicator
                    overlap="circular"
                    anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                    variant="dot"
                  >
                    <WifiIcon color="primary" />
                  </StatusIndicator>
                ) : (
                  <WifiOffIcon color="error" />
                )}
                <Typography variant="body2" color={isConnected ? "primary" : "error"}>
                  {isConnected ? "Online" : "Offline"}
                </Typography>
              </Box>
            </Tooltip>
          </Toolbar>
        </AppBar>
        
        <Divider />
        
        <ChatContainer elevation={3}>
          <MessagesContainer>
            {messages.length === 0 && (
              <Box 
                sx={{ 
                  display: 'flex', 
                  flexDirection: 'column', 
                  alignItems: 'center', 
                  justifyContent: 'center',
                  height: '100%',
                  opacity: 0.7
                }}
              >
                <SmartToyIcon sx={{ fontSize: 60, color: 'primary.main', mb: 2 }} />
                <Typography variant="h6" color="text.secondary" align="center">
                  Welcome to Obsrv AI
                </Typography>
                <Typography variant="body2" color="text.secondary" align="center" sx={{ mt: 1 }}>
                  I'll help with your request. Just tell me what you need!
                </Typography>
              </Box>
            )}
            
            {messages.map((message, index) => (
              <Box key={index} sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, mb: 2 }}>
                {!message.isUser && (
                  <Avatar sx={{ bgcolor: 'primary.dark' }}>
                    <SmartToyIcon />
                  </Avatar>
                )}
                <MessageBubble isUser={message.isUser}>
                  <Typography variant="body1">{message.text}</Typography>
                </MessageBubble>
                {message.isUser && (
                  <Avatar sx={{ bgcolor: 'secondary.dark' }}>
                    <PersonIcon />
                  </Avatar>
                )}
              </Box>
            ))}
            
            {streamingMessage && (
              <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, mb: 2 }}>
                <Avatar sx={{ bgcolor: 'primary.dark' }}>
                  <SmartToyIcon />
                </Avatar>
                <MessageBubble isUser={false}>
                  <Typography variant="body1">{streamingMessage}</Typography>
                </MessageBubble>
              </Box>
            )}
            
            {isLoading && !streamingMessage && (
              <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, mb: 2 }}>
                <Avatar sx={{ bgcolor: 'primary.dark' }}>
                  <SmartToyIcon />
                </Avatar>
                <TypingIndicator>
                  <div className="dot"></div>
                  <div className="dot"></div>
                  <div className="dot"></div>
                </TypingIndicator>
              </Box>
            )}
            
            <div ref={messagesEndRef} />
          </MessagesContainer>
          
          <InputContainer>
            <TextField
              fullWidth
              variant="outlined"
              placeholder="Type your message..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={!isConnected || isLoading}
              multiline
              maxRows={4}
              size="small"
              sx={{
                '& .MuiOutlinedInput-root': {
                  backgroundColor: theme.palette.mode === 'light' ? '#F0F0F0' : '#555555',
                  '& fieldset': {
                    borderColor: 'rgba(255, 255, 255, 0.23)',
                  },
                  '&:hover fieldset': {
                    borderColor: 'primary.main',
                  },
                  '&.Mui-focused fieldset': {
                    borderColor: 'primary.main',
                  },
                },
              }}
            />
            <Tooltip title="Send message">
              <span>
                <IconButton 
                  color="primary" 
                  onClick={handleSend}
                  disabled={!isConnected || !input.trim() || isLoading}
                  sx={{ 
                    bgcolor: 'primary.dark', 
                    '&:hover': { bgcolor: 'primary.main' },
                    '&.Mui-disabled': { bgcolor: 'rgba(255, 255, 255, 0.12)' }
                  }}
                >
                  <SendIcon />
                </IconButton>
              </span>
            </Tooltip>
          </InputContainer>
        </ChatContainer>
        
        <Snackbar 
          open={!!error} 
          autoHideDuration={6000} 
          onClose={handleCloseError}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
          TransitionComponent={Fade}
        >
          <Alert onClose={handleCloseError} severity="error" sx={{ width: '100%' }}>
            {error}
          </Alert>
        </Snackbar>
      </AppContainer>
    </ThemeProvider>
  );
}

export default App; 