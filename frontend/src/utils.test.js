import { describe, expect, it } from 'vitest';

import {
  formatCurrency,
  formatDateTime,
  formatDetailValue,
  riskClass,
  ruleLabel,
  statusClass,
  statusLabel,
  summariseRules,
} from './utils';

describe('formatCurrency', () => {
  it('formats an amount as Indian rupees', () => {
    expect(formatCurrency(45000)).toContain('45,000');
  });

  it('falls back gracefully for missing values', () => {
    expect(formatCurrency(undefined)).toContain('0');
  });
});

describe('formatDateTime', () => {
  it('formats an ISO timestamp', () => {
    expect(formatDateTime('2026-01-02T10:30:00Z')).toMatch(/2026/);
  });

  it('returns n/a for missing or invalid input', () => {
    expect(formatDateTime(null)).toBe('n/a');
    expect(formatDateTime('nonsense')).toBe('n/a');
  });
});

describe('badge helpers', () => {
  it('maps risk levels to css classes', () => {
    expect(riskClass('HIGH')).toBe('badge badge-high');
    expect(riskClass('MEDIUM')).toBe('badge badge-medium');
    expect(riskClass('LOW')).toBe('badge badge-low');
    expect(riskClass(undefined)).toBe('badge');
  });

  it('maps review statuses to css classes', () => {
    expect(statusClass('PENDING_REVIEW')).toBe('badge badge-pending');
    expect(statusClass('CLEARED')).toBe('badge badge-cleared');
    expect(statusClass('CONFIRMED_FRAUD')).toBe('badge badge-fraud');
  });

  it('humanises rule and status names', () => {
    expect(statusLabel('PENDING_REVIEW')).toBe('PENDING REVIEW');
    expect(ruleLabel('impossible_location')).toBe('impossible location');
    expect(summariseRules(['transaction_velocity', 'unusual_amount'])).toBe(
      'transaction velocity, unusual amount',
    );
    expect(summariseRules([])).toBe('none');
  });
});

describe('formatDetailValue', () => {
  it('renders the explanation payload values', () => {
    expect(formatDetailValue(8210.315)).toBe('8210.32');
    expect(formatDetailValue(300)).toBe('300');
    expect(formatDetailValue(true)).toBe('yes');
    expect(formatDetailValue(null)).toBe('n/a');
    expect(formatDetailValue('Chennai, IN')).toBe('Chennai, IN');
  });
});
