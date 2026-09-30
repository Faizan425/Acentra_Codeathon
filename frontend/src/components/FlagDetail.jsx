import { formatCurrency, formatDateTime, formatDetailValue, riskClass, ruleLabel, statusClass, statusLabel } from '../utils';

function InfoRow({ label, value }) {
  return (
    <div className="info-row">
      <span className="info-label">{label}</span>
      <span className="info-value">{value}</span>
    </div>
  );
}

function RuleCard({ detail }) {
  const keys = Object.keys(detail.details || {});
  return (
    <article className={detail.triggered ? 'rule-card rule-card-hit' : 'rule-card'}>
      <header>
        <span className="rule-name">{ruleLabel(detail.rule)}</span>
        <span className={detail.triggered ? 'badge badge-high' : 'badge badge-low'}>
          {detail.triggered ? `+${detail.score}` : 'not triggered'}
        </span>
      </header>
      <p className="rule-reason">{detail.reason}</p>
      {keys.length > 0 && (
        <dl className="rule-details">
          {keys.map((key) => (
            <div key={key}>
              <dt>{ruleLabel(key)}</dt>
              <dd>{formatDetailValue(detail.details[key])}</dd>
            </div>
          ))}
        </dl>
      )}
    </article>
  );
}

export function FlagDetail({ detail, loading, busy, onReview, onClear }) {
  if (loading) return <aside className="detail-panel">Loading details…</aside>;
  if (!detail) {
    return (
      <aside className="detail-panel">
        <h2>Transaction details</h2>
        <p className="muted">Select a flagged transaction to investigate it.</p>
      </aside>
    );
  }

  const tx = detail.transaction || {};

  return (
    <aside className="detail-panel">
      <header className="detail-header">
        <div>
          <h2>Flag #{detail.id}</h2>
          <p className="muted">
            {tx.account_id} · {formatCurrency(tx.amount)}
          </p>
        </div>
        <div className="detail-badges">
          <span className={riskClass(detail.risk_level)}>
            {detail.risk_level} · {detail.risk_score}
          </span>
          <span className={statusClass(detail.status)}>{statusLabel(detail.status)}</span>
        </div>
      </header>

      <section className="detail-section">
        <h3>Transaction</h3>
        <InfoRow label="Transaction ID" value={`#${tx.id ?? detail.transaction_id}`} />
        <InfoRow label="Account" value={tx.account_id} />
        <InfoRow label="Amount" value={formatCurrency(tx.amount)} />
        <InfoRow label="Timestamp" value={formatDateTime(tx.timestamp)} />
        <InfoRow label="Location" value={tx.location || 'n/a'} />
        <InfoRow
          label="Coordinates"
          value={
            tx.latitude != null && tx.longitude != null
              ? `${tx.latitude}, ${tx.longitude}`
              : 'not provided'
          }
        />
      </section>

      <section className="detail-section">
        <h3>Review</h3>
        <InfoRow label="Status" value={statusLabel(detail.status)} />
        <InfoRow label="Reviewed by" value={detail.reviewed_by || 'n/a'} />
        <InfoRow label="Reviewed at" value={formatDateTime(detail.reviewed_at)} />
        <InfoRow
          label="SNS alert (LocalStack)"
          value={detail.alert_published ? 'published' : detail.alert_error || 'not sent'}
        />
        <div className="detail-actions">
          <button
            type="button"
            className="btn btn-primary"
            disabled={busy || detail.status === 'REVIEWED'}
            onClick={() => onReview('REVIEWED')}
          >
            Mark Reviewed
          </button>
          <button
            type="button"
            className="btn"
            disabled={busy || detail.status === 'CONFIRMED_FRAUD'}
            onClick={() => onReview('CONFIRMED_FRAUD')}
          >
            Confirm Fraud
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            disabled={busy || detail.status === 'CLEARED'}
            onClick={onClear}
          >
            Clear
          </button>
          {detail.status !== 'PENDING_REVIEW' && (
            <button
              type="button"
              className="btn btn-ghost"
              disabled={busy}
              onClick={() => onReview('PENDING_REVIEW')}
            >
              Reopen
            </button>
          )}
        </div>
      </section>

      <section className="detail-section">
        <h3>
          Rule evaluation <span className="muted">(every rule reports its verdict)</span>
        </h3>
        {(detail.rule_details || []).map((ruleDetail) => (
          <RuleCard key={ruleDetail.rule} detail={ruleDetail} />
        ))}
      </section>

      <section className="detail-section">
        <h3>Account history</h3>
        {(detail.history || []).length === 0 ? (
          <p className="muted">No other transactions for this account.</p>
        ) : (
          <table className="history-table">
            <thead>
              <tr>
                <th>When</th>
                <th className="num">Amount</th>
                <th>Location</th>
              </tr>
            </thead>
            <tbody>
              {(detail.history || []).map((row) => (
                <tr key={row.id}>
                  <td className="nowrap">{formatDateTime(row.timestamp)}</td>
                  <td className="num">{formatCurrency(row.amount)}</td>
                  <td>{row.location || 'n/a'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </aside>
  );
}
