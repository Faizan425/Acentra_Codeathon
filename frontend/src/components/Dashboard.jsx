export function SummaryCards({ summary }) {
  const cards = [
    { key: 'total_transactions', label: 'Total transactions', tone: 'neutral' },
    { key: 'flagged_transactions', label: 'Flagged', tone: 'flagged' },
    { key: 'high_risk_transactions', label: 'High risk', tone: 'high' },
    { key: 'pending_reviews', label: 'Pending reviews', tone: 'pending' },
    { key: 'cleared_transactions', label: 'Cleared', tone: 'cleared' },
  ];

  return (
    <section className="cards" aria-label="Dashboard summary">
      {cards.map((card) => (
        <article className={`card card-${card.tone}`} key={card.key}>
          <span className="card-label">{card.label}</span>
          <span className="card-value">{summary ? summary[card.key] : '-'}</span>
        </article>
      ))}
    </section>
  );
}

export function EngineBanner({ health, engineInfo }) {
  if (!health && !engineInfo) return null;

  return (
    <section className="engine-banner">
      <div className="engine-item">
        <span className="engine-label">Backend</span>
        <span className={health?.status === 'healthy' ? 'dot dot-ok' : 'dot dot-warn'} />
        <span>{health ? `${health.database} db / ${health.notifications} sns` : 'unknown'}</span>
      </div>
      <div className="engine-item">
        <span className="engine-label">Risk policy</span>
        <span>
          {engineInfo
            ? `LOW 0-${engineInfo.risk_policy.medium_threshold - 1} | MEDIUM ${
                engineInfo.risk_policy.medium_threshold
              }-${engineInfo.risk_policy.high_threshold - 1} | HIGH ${engineInfo.risk_policy.high_threshold}+`
            : 'unknown'}
        </span>
      </div>
      <div className="engine-item engine-rules">
        <span className="engine-label">Rule plugins</span>
        {(engineInfo?.rules || []).map((rule) => (
          <span className="rule-chip" key={rule.name} title={rule.description}>
            {rule.name}
          </span>
        ))}
      </div>
    </section>
  );
}
