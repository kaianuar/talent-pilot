import React, { useState, useRef, useEffect } from 'react';
import {
  Box,
  Paper,
  TextField,
  IconButton,
  Typography,
  Avatar,
  CircularProgress,
  Alert,
  Chip,
  LinearProgress,
  Button,
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import PersonIcon from '@mui/icons-material/Person';
import AttachFileIcon from '@mui/icons-material/AttachFile';
import { useChat, useUploadResume, useSubmitApplication } from '../api/hooks';
import { useAppStore } from '../store';

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: Date;
}

interface ChatInterfaceProps {
  candidateId?: string;
  onCandidateCreated?: (id: string) => void;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({
  candidateId,
  onCandidateCreated,
}) => {
  const chatHistory = useAppStore((s) => s.chatHistory);
  const addStoreMessage = useAppStore((s) => s.addMessage);
  const clearChatHistory = useAppStore((s) => s.clearChat);

  const defaultMessages: Message[] = [
    {
      role: 'assistant',
      content: "Hello! I'm TalentPilot, your AI recruiting assistant. Upload your CV (PDF) and I'll help you find matching job opportunities!",
      timestamp: new Date(),
    },
  ];

  // Restore from persisted store, or use default greeting
  const [messages, setMessages] = useState<Message[]>(() => {
    if (chatHistory.length > 0) {
      return chatHistory.map((m) => ({
        role: m.role as 'user' | 'assistant' | 'system',
        content: m.content,
        timestamp: new Date(m.timestamp),
      }));
    }
    return defaultMessages;
  });
  const [input, setInput] = useState('');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [showSendButton, setShowSendButton] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const chatMutation = useChat();
  const uploadMutation = useUploadResume();
  const submitMutation = useSubmitApplication();
  const selectedJobId = useAppStore((s) => s.selectedJobId);
  const selectedJobTitle = useAppStore((s) => s.selectedJobTitle);
  const matches = useAppStore((s) => s.matches);
  const lastSentApplication = useAppStore((s) => s.lastSentApplication);
  const clearAnnouncedApplication = useAppStore((s) => s.clearAnnouncedApplication);
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Consume the one-shot application announcement from the store. When the
  // ScreeningPanel successfully sends an application, it stashes {jobId,
  // jobTitle} in lastSentApplication just before unmounting. This effect
  // fires once on mount (or after the value changes), appends a system
  // message to the chat, and clears the field so the announcement does
  // not re-fire on subsequent re-renders or remounts.
  useEffect(() => {
    if (!lastSentApplication) return;
    const { jobTitle } = lastSentApplication;
    setMessages((prev) => [
      ...prev,
      {
        role: 'assistant',
        content: `Your application for **${jobTitle}** has been sent to the recruiter. Would you like to start screening for a different job?`,
        timestamp: new Date(),
      },
    ]);
    clearAnnouncedApplication();
  }, [lastSentApplication, clearAnnouncedApplication]);

  // Sync messages to persisted store (survives component unmount)
  useEffect(() => {
    clearChatHistory();
    for (const m of messages) {
      addStoreMessage(m.role, m.content);
    }
  }, [messages]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage: Message = {
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');

    try {
      const response = await chatMutation.mutateAsync({
        messages: messages.concat(userMessage).map((m) => ({
          role: m.role,
          content: m.content,
        })),
        candidateId,
        sendConfirmed: false, // send_confirmed handled via /applications
      });

      const assistantMessage: Message = {
        role: 'assistant',
        content: response.assistant_text,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // Show send-to-recruiter button when assistant mentions applying
      const lower = response.assistant_text.toLowerCase();
      if (/send|apply|email|recruit|application/.test(lower)) {
        setShowSendButton(true);
      }
    } catch {
      const errorMessage: Message = {
        role: 'assistant',
        content: 'I apologize, but I encountered an error processing your request. Please try again.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    }
  };

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadProgress(0);

    try {
      const result = await uploadMutation.mutateAsync({
        file,
        onProgress: (progress) => {
          setUploadProgress(progress.percentage);
        },
      });

      const successMessage: Message = {
        role: 'assistant',
        content: `Great! I've successfully parsed your CV. Welcome, ${result.parsed.name}!\n\nI found ${result.parsed.skills.length} skills and ${result.parsed.years_experience} years of experience. I've matched you against 32 open positions — check the panel on the right and **click a job** to start your screening interview!`,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, successMessage]);
      onCandidateCreated?.(result.candidate_id);
    } catch {
      const errorMessage: Message = {
        role: 'assistant',
        content: 'I apologize, but I encountered an error uploading your CV. Please ensure it\'s a valid PDF file and try again.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Messages Area */}
      <Box
        sx={{
          flex: 1,
          overflow: 'auto',
          p: 2,
          bgcolor: 'background.default',
        }}
      >
        {messages.map((message, index) => (
          <Box
            key={index}
            sx={{
              display: 'flex',
              flexDirection: message.role === 'user' ? 'row-reverse' : 'row',
              mb: 1.5,
              gap: 1.5,
            }}
          >
            <Avatar
              sx={{
                bgcolor: message.role === 'user' ? 'primary.main' : 'secondary.main',
                width: 36,
                height: 36,
              }}
            >
              {message.role === 'user' ? <PersonIcon sx={{ fontSize: 20 }} /> : <SmartToyIcon sx={{ fontSize: 20 }} />}
            </Avatar>
            <Paper
              elevation={0}
              sx={{
                p: 1.5,
                maxWidth: '70%',
                bgcolor: message.role === 'user' ? 'primary.main' : 'background.paper',
                color: message.role === 'user' ? 'primary.contrastText' : 'text.primary',
                borderRadius: message.role === 'user' ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
              }}
            >
              <Typography
                variant="body2"
                sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: 1.55 }}
              >
                {message.content}
              </Typography>
            </Paper>
          </Box>
        ))}

        {/* Loading indicator */}
        {(chatMutation.isPending || isUploading) && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, ml: 6, mb: 2 }}>
            <CircularProgress size={20} />
            <Typography variant="body2" color="text.secondary">
              {isUploading ? 'Uploading your CV...' : 'Thinking...'}
            </Typography>
          </Box>
        )}

        {/* Upload progress */}
        {isUploading && uploadProgress > 0 && (
          <Box sx={{ ml: 6, mb: 2, maxWidth: '50%' }}>
            <LinearProgress variant="determinate" value={uploadProgress} />
            <Typography variant="caption" color="text.secondary">
              {uploadProgress}%
            </Typography>
          </Box>
        )}

        <div ref={messagesEndRef} />
      </Box>

      {/* Error display */}
      {uploadMutation.isError && (
        <Alert severity="error" sx={{ mx: 2, mt: 1 }}>
          Failed to upload CV. Please try again with a valid PDF file.
        </Alert>
      )}

      {/* Input Area */}
      <Box
        sx={{
          p: 2,
          bgcolor: 'background.paper',
          borderTop: '1px solid',
          borderColor: 'divider',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {/* File upload button */}
          <input
            type="file"
            accept=".pdf"
            ref={fileInputRef}
            onChange={handleFileSelect}
            style={{ display: 'none' }}
          />
          <IconButton
            color="primary"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading || chatMutation.isPending}
            title="Upload CV (PDF)"
          >
            <AttachFileIcon />
          </IconButton>

          {/* Text input */}
          <TextField
            fullWidth
            variant="outlined"
            placeholder="Type your message..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            disabled={chatMutation.isPending || isUploading}
            size="small"
          />

          {/* Send button */}
          <IconButton
            color="primary"
            onClick={handleSend}
            disabled={!input.trim() || chatMutation.isPending || isUploading}
          >
            <SendIcon />
          </IconButton>
        </Box>

        <Box sx={{ display: 'flex', gap: 0.75, mt: 1.5, flexWrap: 'wrap' }}>
          <Chip
            size="small"
            label="Show my matches"
            onClick={() => setInput('Show me my job matches')}
            variant="outlined"
            clickable
            sx={{ borderColor: 'divider', '&:hover': { bgcolor: 'secondary.light', borderColor: 'secondary.main' } }}
          />
          <Chip
            size="small"
            label="Apply to a job"
            onClick={() => setInput('I want to apply for a job')}
            variant="outlined"
            clickable
            sx={{ borderColor: 'divider', '&:hover': { bgcolor: 'secondary.light', borderColor: 'secondary.main' } }}
          />
          <Chip
            size="small"
            label="View my profile"
            onClick={() => setInput('Show my profile')}
            variant="outlined"
            clickable
            sx={{ borderColor: 'divider', '&:hover': { bgcolor: 'secondary.light', borderColor: 'secondary.main' } }}
          />
        </Box>

        {/* Send to Recruiter confirmation */}
        {showSendButton && selectedJobId && (
          <Box sx={{ mt: 2, p: 2, bgcolor: 'success.light', borderRadius: 1 }}>
            <Typography variant="body2" sx={{ mb: 1, color: 'success.contrastText' }}>
              Apply to <strong>{selectedJobTitle}</strong>? This will email the recruiter with your profile.
            </Typography>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                variant="contained"
                color="success"
                size="small"
                disabled={chatMutation.isPending || isUploading || submitMutation.isPending}
                onClick={async () => {
                  if (!candidateId) return;
                  const match = matches.find(m => m.job_id === selectedJobId);
                  try {
                    await submitMutation.mutateAsync({
                      candidateId,
                      jobId: selectedJobId,
                      matchScore: match?.match_score ?? 0,
                      matchTier: match?.tier ?? 'CONFIRMED',
                    });
                    setMessages((prev) => [...prev, {
                      role: 'assistant',
                      content: `✅ Your application for **${selectedJobTitle}** has been sent to the recruiter!`,
                      timestamp: new Date(),
                    }]);
                  } catch {
                    setMessages((prev) => [...prev, {
                      role: 'assistant',
                      content: '⚠️ Failed to send application. Please try again.',
                      timestamp: new Date(),
                    }]);
                  }
                  setShowSendButton(false);
                }}
              >
                {submitMutation.isPending ? 'Sending...' : 'Send to Recruiter'}
              </Button>
              <Button
                variant="outlined"
                size="small"
                onClick={() => setShowSendButton(false)}
              >
                Cancel
              </Button>
            </Box>
          </Box>
        )}
      </Box>
    </Box>
  );
};

export default ChatInterface;
