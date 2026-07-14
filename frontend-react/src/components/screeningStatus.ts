/**
 * Map a ScreeningSummary.status (lowercase wire format from
 * backend.domain.entities.screening_session.ScreeningStatus) to a
 * candidate-facing label. The exact mechanism (complete vs.
 * early_termination, with or without sufficient evidence) is hidden
 * from the candidate — the friendly message body below the chips makes
 * the actual outcome clear.
 *
 *   'complete'            -> 'Screening Passed'
 *   'early_termination'   -> 'Screening Passed'
 *   'rejected'            -> 'Screening Failed'
 *   anything else         -> 'In Progress' (defensive fallback)
 */
export function formatScreeningStatus(status: string | undefined): string {
  switch (status) {
    case 'complete':
    case 'early_termination':
      return 'Screening Passed';
    case 'rejected':
      return 'Screening Failed';
    default:
      return 'In Progress';
  }
}
