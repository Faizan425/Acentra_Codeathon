import {
  formatCurrency,
  formatDateTime,
  riskClass,
  statusClass,
  statusLabel,
  summariseRules,
} from '../utils';

export function FlagTable({
  flags,
  selectedId,
  onSelect,
  onReview,
  onClear,
  busyId,
}) {
  if (!flags || flags.length === 0) {
    return (
      <div className="empty-state">
        <p>No flagged transactions match the current filters.</p>
        <p className="muted">
          Seed the demo data with <code>docker compose exec backend python seed.py</code>.
        </p>
      </div>
    );
  }

  return (
    <div className="table-wrapper">
      <table className="flag-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Account</th>
            <th className="num">Amount</th>
            <th>Timestamp</th>
            <th>Location</th>
            <th className="num">Score</th>
            <th>Level</th>
            <th>Status</th>
            <th>Triggered rules</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {flags.map((flag) => {
            const tx = flag.transaction || {};
            const isBusy = busyId === flag.id;
            return (
              <tr
                key={flag.id}
                className={selectedId === flag.id ? 'selected' : undefined}
                onClick={() => onSelect(flag.id)}
              >
                <td>#{flag.id}</td>
                <td>{tx.account_id}</td>
                <td className="num">{formatCurrency(tx.amount)}</td>
                <td className="nowrap">{formatDateTime(tx.timestamp)}</td>
                <td>{tx.location || 'n/a'}</td>
                <td className="num score">{flag.risk_score}</td>
                <td>
                  <span className={riskClass(flag.risk_level)}>{flag.risk_level}</span>
                </td>
                <td>
                  <span className={statusClass(flag.status)}>{statusLabel(flag.status)}</span>
                </td>
                <td className="rules-cell">{summariseRules(flag.triggered_rules)}</td>
                <td className="actions">
                  <button
                    type="button"
                    className="btn btn-small"
                    disabled={isBusy || flag.status === 'REVIEWED'}
                    onClick={(event) => {
                      event.stopPropagation();
                      onReview(flag);
                    }}
                  >
                    Review
                  </button>
                  <button
                    type="button"
                    className="btn btn-small btn-ghost"
                    disabled={isBusy || flag.status === 'CLEARED'}
                    onClick={(event) => {
                      event.stopPropagation();
                      onClear(flag);
                    }}
                  >
                    Clear
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
