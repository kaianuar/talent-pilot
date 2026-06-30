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

/** Warm, muted palette for skill chips by proficiency */
const SKILL_COLORS: Record<string, { bg: string; color: string }> = {
  expert:  { bg: '#6B4D57', color: '#fff' },
  advanced:{ bg: '#896A67', color: '#fff' },
  intermediate: { bg: '#DDC8C4', color: '#13070C' },
};

const skillColor = (level?: string) =>
  SKILL_COLORS[level ?? ''] ?? { bg: '#E8E0DC', color: '#13070C' };

const cardSx = {
  mb: 1.5,
  borderRadius: 2,
  boxShadow: '0 1px 4px rgba(19,7,12,0.06)',
  border: '1px solid',
  borderColor: 'divider',
};

const sectionHeaderSx = {
  display: 'flex',
  alignItems: 'center',
  gap: 1,
  mb: 1.5,
};

const CandidateProfile: React.FC<CandidateProfileProps> = ({ candidateId }) => {
  const { data: candidate, isLoading, isError } = useCandidate(candidateId || '', {
    enabled: !!candidateId,
  });

  if (!candidateId) {
    return (
      <Box sx={{ p: 1.5 }}>
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
      <Box sx={{ p: 1.5 }}>
        <Typography variant="h6" gutterBottom>
          Your Profile
        </Typography>
        <Skeleton variant="circular" width={72} height={72} sx={{ mx: 'auto', mb: 2 }} />
        <Skeleton variant="text" height={30} sx={{ mb: 1 }} />
        <Skeleton variant="text" height={20} sx={{ mb: 1 }} />
        <Skeleton variant="rectangular" height={100} sx={{ mt: 2, borderRadius: 2 }} />
      </Box>
    );
  }

  if (isError || !candidate) {
    return (
      <Box sx={{ p: 1.5 }}>
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
    <Box sx={{ p: 1.5 }}>
      <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
        Your Profile
      </Typography>

      {/* Header Card */}
      <Card sx={cardSx}>
        <CardContent sx={{ pb: '16px !important' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1.5 }}>
            <Avatar
              sx={{
                width: 72,
                height: 72,
                background: 'linear-gradient(135deg, #6B4D57 0%, #896A67 100%)',
                fontSize: '1.5rem',
                fontWeight: 600,
                boxShadow: '0 4px 12px rgba(107,77,87,0.3)',
              }}
            >
              {candidate.name.split(' ').map(n => n[0]).join('').toUpperCase()}
            </Avatar>
            <Box>
              <Typography variant="h6" component="div" sx={{ fontWeight: 600, lineHeight: 1.3 }}>
                {candidate.name}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {candidate.years_experience} years experience
              </Typography>
            </Box>
          </Box>

          <Divider sx={{ mb: 1 }} />

          <List dense disablePadding>
            {candidate.email && (
              <ListItem disablePadding sx={{ mb: 0.25 }}>
                <ListItemIcon sx={{ minWidth: 36 }}>
                  <EmailIcon fontSize="small" sx={{ color: 'secondary.main' }} />
                </ListItemIcon>
                <ListItemText primary={candidate.email} slotProps={{ primary: { variant: 'body2' } }} />
              </ListItem>
            )}
            {candidate.phone && (
              <ListItem disablePadding sx={{ mb: 0.25 }}>
                <ListItemIcon sx={{ minWidth: 36 }}>
                  <PhoneIcon fontSize="small" sx={{ color: 'secondary.main' }} />
                </ListItemIcon>
                <ListItemText primary={candidate.phone} slotProps={{ primary: { variant: 'body2' } }} />
              </ListItem>
            )}
            {candidate.location && (
              <ListItem disablePadding sx={{ mb: 0.25 }}>
                <ListItemIcon sx={{ minWidth: 36 }}>
                  <LocationOnIcon fontSize="small" sx={{ color: 'secondary.main' }} />
                </ListItemIcon>
                <ListItemText primary={candidate.location} slotProps={{ primary: { variant: 'body2' } }} />
              </ListItem>
            )}
          </List>
        </CardContent>
      </Card>

      {/* Skills */}
      <Card sx={cardSx}>
        <CardContent>
          <Box sx={sectionHeaderSx}>
            <CodeIcon sx={{ color: 'primary.main' }} />
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
              Skills
            </Typography>
            <Chip size="small" label={candidate.skills.length} color="primary" sx={{ ml: 0.5 }} />
          </Box>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
            {candidate.skills.map((skill, index) => {
              const { bg, color } = skillColor(skill.level);
              return (
                <Chip
                  key={index}
                  label={skill.name}
                  size="small"
                  sx={{ bgcolor: bg, color, fontWeight: 500, borderRadius: '6px' }}
                />
              );
            })}
          </Box>
        </CardContent>
      </Card>

      {/* Experience */}
      {candidate.experience.length > 0 && (
        <Card sx={cardSx}>
          <CardContent>
            <Box sx={sectionHeaderSx}>
              <WorkIcon sx={{ color: 'primary.main' }} />
              <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                Experience
              </Typography>
            </Box>
            {candidate.experience.slice(0, 3).map((exp, index) => (
              <Box key={index} sx={{ mb: 1.5, '&:last-of-type': { mb: 0 } }}>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {exp.title}
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
                  {exp.company}{exp.location && ` · ${exp.location}`}
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.25 }}>
                  {exp.start_date} – {exp.end_date || 'Present'}
                </Typography>
                {index < Math.min(candidate.experience.length, 3) - 1 && (
                  <Divider sx={{ mt: 1.5, borderColor: 'divider' }} />
                )}
              </Box>
            ))}
            {candidate.experience.length > 3 && (
              <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                +{candidate.experience.length - 3} more positions
              </Typography>
            )}
          </CardContent>
        </Card>
      )}

      {/* Education */}
      {candidate.education.length > 0 && (
        <Card sx={{ ...cardSx, mb: 0 }}>
          <CardContent>
            <Box sx={sectionHeaderSx}>
              <SchoolIcon sx={{ color: 'primary.main' }} />
              <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                Education
              </Typography>
            </Box>
            {candidate.education.map((edu, index) => (
              <Box key={index} sx={{ mb: index < candidate.education.length - 1 ? 1.5 : 0 }}>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {edu.degree}{edu.field && ` in ${edu.field}`}
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic', mt: 0.25 }}>
                  {edu.institution}
                </Typography>
                {edu.graduation_date && (
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.25 }}>
                    Graduated: {edu.graduation_date}
                  </Typography>
                )}
                {index < candidate.education.length - 1 && (
                  <Divider sx={{ mt: 1.5, borderColor: 'divider' }} />
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
