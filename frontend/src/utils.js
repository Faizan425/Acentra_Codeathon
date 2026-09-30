/**
 * Pure formatting helpers. Kept free of React so they can be unit tested
 * directly with vitest.
 */

export const RISK_LEVELS = ['LOW', 'MEDIUM', 'HIGH'];

export const REVIEW_STATUSES = [
  'PENDING_REVIEW',
  'REVIEWED',
  'CLEARED',
  'CONFIRMED_FRAUD',
];

export function formatCurrency(amount, currency = 'INR') {
  const value = Number(amount ?? 0);
  if (Number.isNaN(value)) return 'n/a';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency,
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatDateTime(isoString) {
  if (!isoString) return 'n/a';
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return 'n/a';
  return date.toLocaleString('en-GB', {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export function riskClass(level) {
  switch (level) {
    case 'HIGH':
      return 'badge badge-high';
    case 'MEDIUM':
      return 'badge badge-medium';
    case 'LOW':
      return 'badge badge-low';
    default:
      return 'badge';
  }
}

export function statusClass(status) {
  switch (status) {
    case 'PENDING_REVIEW':
      return 'badge badge-pending';
    case 'REVIEWED':
      return 'badge badge-reviewed';
    case 'CLEARED':
      return 'badge badge-cleared';
    case 'CONFIRMED_FRAUD':
      return 'badge badge-fraud';
    default:
      return 'badge';
  }
}

export function statusLabel(status) {
  if (!status) return 'UNKNOWN';
  return status.replaceAll('_', ' ');
}

export function ruleLabel(ruleName) {
  if (!ruleName) return 'unknown';
  return ruleName.replaceAll('_', ' ');
}

export function summariseRules(rules) {
  if (!rules || rules.length === 0) return 'none';
  return rules.map(ruleLabel).join(', ');
}

/**
 * Renders a rule detail value for the reviewer console.
 * Distances/speeds/etc. come straight from the backend explanation payload.
 */
export function formatDetailValue(value) {
  if (value === null || value === undefined) return 'n/a';
  if (typeof value === 'number') {
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }
  if (typeof value === 'boolean') return value ? 'yes' : 'no';
  return String(value);
}
