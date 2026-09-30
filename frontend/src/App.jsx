import { useCallback, useEffect, useState } from 'react';

import { api, apiBaseUrl } from './api';
import { EngineBanner, SummaryCards } from './components/Dashboard';
import { FlagDetail } from './components/FlagDetail';
import { FlagTable } from './components/FlagTable';
import { REVIEW_STATUSES, statusLabel } from './utils';

const EMPTY_FILTERS = { status: '', risk_level: '', account_id: '' };

export default function App() {
  const [summary, setSummary] = useState(null);
  const [health, setHealth] = useState(null);
  const [engineInfo, setEngineInfo] = useState(null);
  const [flags, setFlags] = useState([]);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  const loadOverview = useCallback(async () => {
    try {
      const [summaryData, flagsData] = await Promise.all([
        api.summary(),
        api.listFlags(filters),
      ]);
      setSummary(summaryData);
      setFlags(flagsData.items);
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  }, [filters]);

  const loadMeta = useCallback(async () => {
    const [healthResult, engineResult] = await Promise.allSettled([api.health(), api.engineInfo()]);
    if (healthResult.status === 'fulfilled') setHealth(healthResult.value);
    if (engineResult.status === 'fulfilled') setEngineInfo(engineResult.value);
  }, []);

  useEffect(() => {
    loadOverview();
  }, [loadOverview]);

  useEffect(() => {
    loadMeta();
  }, [loadMeta]);

  const openDetail = useCallback(async (flagId) => {
    setSelectedId(flagId);
    setDetailLoading(true);
    try {
      setDetail(await api.getFlag(flagId));
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const runAction = useCallback(
    async (flag, action) => {
      setBusyId(flag.id);
      setNotice(null);
      try {
        const result =
          action === 'clear' ? await api.clearFlag(flag.id, {}) : await api.reviewFlag(flag.id, { status: action });
        setNotice(result.message);
        setError(null);
        await loadOverview();
        if (selectedId === flag.id) await openDetail(flag.id);
      } catch (err) {
        setError(err.message);
      } finally {
        setBusyId(null);
      }
    },
    [loadOverview, openDetail, selectedId],
  );

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>Fraud Review Console</h1>
          <p className="muted">
            Rule based transaction screening · API <code>{apiBaseUrl}</code>
          </p>
        </div>
        <button type="button" className="btn" onClick={() => { loadOverview(); loadMeta(); }}>
          Refresh
        </button>
      </header>

      <EngineBanner health={health} engineInfo={engineInfo} />
      <SummaryCards summary={summary} />

      <section className="filters">
        <label>
          Status
          <select
            value={filters.status}
            onChange={(event) => setFilters({ ...filters, status: event.target.value })}
          >
            <option value="">All</option>
            {REVIEW_STATUSES.map((value) => (
              <option key={value} value={value}>
                {statusLabel(value)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Risk level
          <select
            value={filters.risk_level}
            onChange={(event) => setFilters({ ...filters, risk_level: event.target.value })}
          >
            <option value="">All</option>
            <option value="HIGH">HIGH</option>
            <option value="MEDIUM">MEDIUM</option>
            <option value="LOW">LOW</option>
          </select>
        </label>
        <label>
          Account
          <input
            type="text"
            placeholder="ACC-…"
            value={filters.account_id}
            onChange={(event) => setFilters({ ...filters, account_id: event.target.value })}
          />
        </label>
        <button type="button" className="btn btn-ghost" onClick={() => setFilters(EMPTY_FILTERS)}>
          Reset filters
        </button>
      </section>

      {error && <div className="alert alert-error">{error}</div>}
      {notice && <div className="alert alert-info">{notice}</div>}

      <main className="layout">
        <section className="list-panel">
          <h2>
            Flagged transactions <span className="muted">({flags.length})</span>
          </h2>
          <FlagTable
            flags={flags}
            selectedId={selectedId}
            onSelect={openDetail}
            onReview={(flag) => runAction(flag, 'REVIEWED')}
            onClear={(flag) => runAction(flag, 'clear')}
            busyId={busyId}
          />
        </section>

        <FlagDetail
          detail={detail}
          loading={detailLoading}
          busy={busyId != null}
          onReview={(status) => runAction({ id: detail.id }, status)}
          onClear={() => runAction({ id: detail.id }, 'clear')}
        />
      </main>

      <footer className="app-footer">
        <span className="muted">
          Demo prototype - risk scores are illustrative and computed on the backend only.
        </span>
      </footer>
    </div>
  );
}
