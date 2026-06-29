import React from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Avatar,
  Chip,
  Divider,

  Alert,
  Skeleton,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
} from '@mui/material';
import PersonIcon from '@mui/icons-material/Person';
import EmailIcon from '@mui/icons-material/Email';
import PhoneIcon from '@mui/icons-material/Phone';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import WorkIcon from '@mui/icons-material/Work';
import SchoolIcon from '@mui/icons-material/School';
import CodeIcon from '@mui/icons-material/Code';

import { useCandidate } from '../api/hooks';

interface CandidateProfileProps {
  candidateId?: string;
}

const CandidateProfile: React.FC<CandidateProfileProps> = ({ candidateId }) => {
  const { data: candidate, isLoading, isError } = useCandidate(candidateId || '', {
    enabled: !!candidateId,
  });

  if (!candidateId) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>
          Your Profile
        </Typography>
        <Alert severity="info" icon={<PersonIcon />}>
          Upload your CV to see your profile details!
        </Alert>
      </Box>
    );
  }

  if (isLoading) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>
          Your Profile
        </Typography>
        <Skeleton variant="circular" width={80} height={80} sx={{ mx: 'auto', mb: 2 }} />
        <Skeleton variant="text" height={30} sx={{ mb: 1 }} />
        <Skeleton variant="text" height={20} sx={{ mb: 1 }} />
        <Skeleton variant="rectangular" height={100} sx={{ mt: 2 }} />
      </Box>
    );
  }

  if (isError || !candidate) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>
          Your Profile
        </Typography>
        <Alert severity="error">
          Failed to load candidate profile. Please try again later.
        </Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 2 }}>
      <Typography variant="h6" gutterBottom>
        Your Profile
      </Typography>

      {/* Header Card */}
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
            <Avatar
              sx={{
                width: 64,
                height: 64,
                bgcolor: 'primary.main',
                fontSize: '1.5rem',
              }}
            >
              {candidate.name.split(' ').map(n => n[0]).join('').toUpperCase()}
            </Avatar>
            <Box>
              <Typography variant="h6" component="div">
                {candidate.name}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {candidate.years_experience} years experience
              </Typography>
            </Box>
          </Box>

          <List dense disablePadding>
            {candidate.email && (
              <ListItem disablePadding sx={{ mb: 0.5 }}>
                <ListItemIcon sx={{ minWidth: 32 }}>
                  <EmailIcon fontSize="small" color="action" />
                </ListItemIcon>
                <ListItemText primary={candidate.email} slotProps={{ primary: { variant: 'body2' } }} />
              </ListItem>
            )}
            {candidate.phone && (
              <ListItem disablePadding sx={{ mb: 0.5 }}>
                <ListItemIcon sx={{ minWidth: 32 }}>
                  <PhoneIcon fontSize="small" color="action" />
                </ListItemIcon>
                <ListItemText primary={candidate.phone} slotProps={{ primary: { variant: 'body2' } }} />
              </ListItem>
            )}
            {candidate.location && (
              <ListItem disablePadding sx={{ mb: 0.5 }}>
                <ListItemIcon sx={{ minWidth: 32 }}>
                  <LocationOnIcon fontSize="small" color="action" />
                </ListItemIcon>
                <ListItemText primary={candidate.location} slotProps={{ primary: { variant: 'body2' } }} />
              </ListItem>
            )}
          </List>
        </CardContent>
      </Card>

      {/* Skills */}
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
            <CodeIcon color="primary" />
            <Typography variant="subtitle1" sx={{ fontWeight: 'medium' }}>
              Skills
            </Typography>
            <Chip size="small" label={candidate.skills.length} color="primary" />
          </Box>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
            {candidate.skills.map((skill, index) => (
              <Chip
                key={index}
                label={skill.name}
                size="small"
                variant="outlined"
                color={skill.level === 'expert' ? 'primary' : 'default'}
              />
            ))}
          </Box>
        </CardContent>
      </Card>

      {/* Experience */}
      {candidate.experience.length > 0 && (
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
              <WorkIcon color="primary" />
              <Typography variant="subtitle1" sx={{ fontWeight: 'medium' }}>
                Experience
              </Typography>
            </Box>
            {candidate.experience.slice(0, 3).map((exp, index) => (
              <Box key={index} sx={{ mb: 2, '&:last-child': { mb: 0 } }}>
                <Typography variant="body2" sx={{ fontWeight: 'medium' }}>
                  {exp.title}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {exp.company} {exp.location && `• ${exp.location}`}
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                  {exp.start_date} - {exp.end_date || 'Present'}
                </Typography>
                {index < Math.min(candidate.experience.length, 3) - 1 && (
                  <Divider sx={{ mt: 2 }} />
                )}
              </Box>
            ))}
            {candidate.experience.length > 3 && (
              <Typography variant="caption" color="text.secondary">
                +{candidate.experience.length - 3} more positions
              </Typography>
            )}
          </CardContent>
        </Card>
      )}

      {/* Education */}
      {candidate.education.length > 0 && (
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
              <SchoolIcon color="primary" />
              <Typography variant="subtitle1" sx={{ fontWeight: 'medium' }}>
                Education
              </Typography>
            </Box>
            {candidate.education.map((edu, index) => (
              <Box key={index}>
                <Typography variant="body2" sx={{ fontWeight: 'medium' }}>
                  {edu.degree} {edu.field && `in ${edu.field}`}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {edu.institution}
                </Typography>
                {edu.graduation_date && (
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                    Graduated: {edu.graduation_date}
                  </Typography>
                )}
              </Box>
            ))}
          </CardContent>
        </Card>
      )}
    </Box>
  );
};

export default CandidateProfile;
