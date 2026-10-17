import React from 'react';
import { interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { Background } from '../components/Background';
import { Header } from '../components/Header';
import { CodeBlock } from '../components/CodeBlock';
import { Captions } from '../components/Captions';
import { SubtitleEntry } from '../types';

export const Scene4WarStories: React.FC<{ subtitles: SubtitleEntry[] }> = ({ subtitles }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleSpring = spring({
    frame,
    fps,
    config: { damping: 14, stiffness: 80 },
  });

  // Switch between Incident 07 and Incident 14 halfway through the scene
  // Duration: ~34.1s = 1023 frames
  const isSecondHalf = frame > 510;

  const incidentCode1 = `
# Incident #07 Fix: Lexicographically sort UUIDs
# Eliminates circular-wait deadlocks across concurrent transfers
lock_keys = [f"lock:acc:{u}" for u in sorted(account_ids)]

for key in lock_keys:
    acquired = await lock_service.acquire(key, timeout_ms=5000)
    if not acquired:
        raise LockAcquisitionError(f"Deadlock avoided: {key}")
`;

  const incidentCode2 = `
# Incident #14 Fix: Native SQLAlchemy Compare-And-Swap
# Prevents in-memory increment without SQL WHERE version = CAS
class Account(Base):
    __tablename__ = "accounts"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    version: Mapped[int] = mapped_column(default=1)
    
    __mapper_args__ = {"version_id_col": version}
`;

  return (
    <div style={{ position: 'relative', width: 1920, height: 1080, overflow: 'hidden' }}>
      <Background accentColor="#a855f7" />
      <Header sceneNumber="SCENE 04" sceneTag="Distributed Systems Postmortems" />

      {/* Main Content Area */}
      <div
        style={{
          position: 'absolute',
          top: 130,
          left: 100,
          right: 100,
          bottom: 120,
          display: 'flex',
          flexDirection: 'column',
          gap: 28,
          zIndex: 10,
        }}
      >
        {/* Title */}
        <div
          style={{
            transform: `translateY(${(1 - titleSpring) * 30}px)`,
            opacity: titleSpring,
            textAlign: 'center',
          }}
        >
          <div
            style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 14,
              fontWeight: 800,
              color: '#c084fc',
              letterSpacing: '0.15em',
              textTransform: 'uppercase',
              marginBottom: 4,
            }}
          >
            REAL-WORLD HARDENED PRODUCTION LESSONS
          </div>
          <h1
            style={{
              fontFamily: 'Inter, system-ui, sans-serif',
              fontSize: 48,
              fontWeight: 900,
              color: '#ffffff',
              letterSpacing: '-0.03em',
              margin: 0,
            }}
          >
            {isSecondHalf
              ? 'Incident #14: Fake OCC vs. Native Database CAS'
              : 'Incident #07: Circular Deadlocks & UUID Ordering'}
          </h1>
        </div>

        {/* Two-Column Layout */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1.3fr',
            gap: 36,
            alignItems: 'center',
          }}
        >
          {/* Left Column: Problem & Root Cause Breakdown */}
          <div
            style={{
              borderRadius: 20,
              padding: 32,
              backgroundColor: 'rgba(15, 23, 42, 0.9)',
              border: '1px solid rgba(168, 85, 247, 0.3)',
              boxShadow: '0 20px 45px rgba(0, 0, 0, 0.7), 0 0 30px rgba(168, 85, 247, 0.15)',
              display: 'flex',
              flexDirection: 'column',
              gap: 16,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 24 }}>{isSecondHalf ? '⚠️' : '🔄'}</span>
              <span
                style={{
                  fontFamily: 'JetBrains Mono, monospace',
                  fontSize: 12,
                  fontWeight: 800,
                  color: isSecondHalf ? '#f59e0b' : '#ef4444',
                  backgroundColor: isSecondHalf ? 'rgba(245, 158, 11, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                  padding: '4px 10px',
                  borderRadius: 6,
                }}
              >
                {isSecondHalf ? 'HIGH RISK ARCHITECTURAL BUG' : 'CRITICAL PRODUCTION DEADLOCK'}
              </span>
            </div>

            <div
              style={{
                fontFamily: 'Inter, system-ui, sans-serif',
                fontSize: 18,
                fontWeight: 800,
                color: '#ffffff',
                lineHeight: 1.3,
              }}
            >
              {isSecondHalf
                ? 'Silent Lost Updates via In-Memory Version Increments'
                : 'Mutual Lock Waiting in Bidirectional Concurrent Transfers'}
            </div>

            <div
              style={{
                fontFamily: 'Inter, system-ui, sans-serif',
                fontSize: 14,
                lineHeight: 1.6,
                color: '#94a3b8',
              }}
            >
              {isSecondHalf ? (
                <>
                  <strong style={{ color: '#e2e8f0' }}>The Vulnerability:</strong> Incrementing{' '}
                  <code style={{ color: '#f87171' }}>acc.version += 1</code> in application RAM does
                  not emit a version check in the SQL WHERE clause, allowing concurrent updates to
                  overwrite ledger state silently.
                  <br />
                  <br />
                  <strong style={{ color: '#34d399' }}>The Solution:</strong> Configuring{' '}
                  <code style={{ color: '#38bdf8' }}>version_id_col</code> enforces atomic CAS on
                  every UPDATE statement: <code style={{ color: '#c084fc' }}>WHERE version = :cas</code>.
                </>
              ) : (
                <>
                  <strong style={{ color: '#e2e8f0' }}>The Vulnerability:</strong> Thread 1 locked
                  Account A then B. Thread 2 locked Account B then A. Both threads timed out waiting
                  for the other, halting payments.
                  <br />
                  <br />
                  <strong style={{ color: '#34d399' }}>The Solution:</strong> Enforcing global
                  lexicographical sorting on all UUID keys before lock acquisition destroys Coffman
                  condition #4, making circular wait deadlocks mathematically impossible.
                </>
              )}
            </div>
          </div>

          {/* Right Column: Code Block Inspector */}
          <CodeBlock
            filename={isSecondHalf ? 'app/models/account.py' : 'app/services/lock_manager.py'}
            code={isSecondHalf ? incidentCode2 : incidentCode1}
            highlightLines={isSecondHalf ? [10] : [3, 6, 7]}
            incidentBadge={isSecondHalf ? 'SQLAlchemy Native CAS' : 'Redlock UUID Mutex'}
            badgeType="fix"
          />
        </div>
      </div>

      <Captions subtitles={subtitles} />
    </div>
  );
};
