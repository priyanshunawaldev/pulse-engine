import React from 'react';
import { interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { Background } from '../components/Background';
import { Header } from '../components/Header';
import { Captions } from '../components/Captions';
import { SubtitleEntry } from '../types';

const PIPELINE_STAGES = [
  {
    num: '01',
    name: 'Token Bucket Rate Limiter',
    tech: 'Redis 7 Memory Store',
    desc: 'Absorbs DDoS & burst bot storms before touching relational storage.',
    icon: '⏳',
    color: '#38bdf8',
  },
  {
    num: '02',
    name: 'SHA-256 Idempotency Gate',
    tech: 'FastAPI + Postgres / Redis',
    desc: 'Hashes payload key. Guarantees network retries never double-charge.',
    icon: '🔑',
    color: '#a855f7',
  },
  {
    num: '03',
    name: 'Redlock Distributed Mutex',
    tech: 'Sorted UUIDs + Lua Script',
    desc: 'Multi-resource locking ordered by UUID, eliminating circular deadlocks.',
    icon: '🔒',
    color: '#f43f5e',
  },
  {
    num: '04',
    name: 'Double-Entry Invariant Check',
    tech: 'Mathematical Kernel',
    desc: 'Enforces debits equal credits: Σ entries == 0.0000 across all journals.',
    icon: '⚖️',
    color: '#10b981',
  },
  {
    num: '05',
    name: 'Postgres Optimistic CAS',
    tech: 'version_id_col ORM Mapper',
    desc: 'Native database Compare-And-Swap rejects concurrent stale updates.',
    icon: '💾',
    color: '#3b82f6',
  },
  {
    num: '06',
    name: 'HMAC Webhooks & Dead Letter',
    tech: 'Celery Workers + SHA256',
    desc: 'Asynchronous event dispatch with HMAC signatures and exponential backoff.',
    icon: '📡',
    color: '#eab308',
  },
];

export const Scene2Architecture: React.FC<{ subtitles: SubtitleEntry[] }> = ({ subtitles }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleSpring = spring({
    frame,
    fps,
    config: { damping: 14, stiffness: 80 },
  });

  // Calculate active stage based on frame (each gets highlighted sequentially)
  const totalStages = PIPELINE_STAGES.length;
  const { durationInFrames } = useVideoConfig();
  const stageDurationFrames = Math.max(1, Math.floor(durationInFrames / totalStages));
  const currentActiveIdx = Math.min(totalStages - 1, Math.floor(frame / stageDurationFrames));

  return (
    <div style={{ position: 'relative', width: 1920, height: 1080, overflow: 'hidden' }}>
      <Background accentColor="#38bdf8" />
      <Header sceneNumber="SCENE 02" sceneTag="Zero-Trust Architecture" />

      {/* Main Content Area */}
      <div
        style={{
          position: 'absolute',
          top: 130,
          left: 80,
          right: 80,
          bottom: 120,
          display: 'flex',
          flexDirection: 'column',
          gap: 28,
          zIndex: 10,
        }}
      >
        {/* Title & Subtitle */}
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
              color: '#38bdf8',
              letterSpacing: '0.15em',
              textTransform: 'uppercase',
              marginBottom: 6,
            }}
          >
            MATHEMATICALLY FORMALIZED LEDGER PIPELINE
          </div>
          <h1
            style={{
              fontFamily: 'Inter, system-ui, sans-serif',
              fontSize: 52,
              fontWeight: 900,
              color: '#ffffff',
              letterSpacing: '-0.03em',
              margin: 0,
            }}
          >
            The 6-Stage Defense In Depth
          </h1>
        </div>

        {/* 6 Stages Grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: 24,
            padding: '10px 0',
          }}
        >
          {PIPELINE_STAGES.map((stage, idx) => {
            const cardSpring = spring({
              frame: Math.max(0, frame - idx * 10),
              fps,
              config: { damping: 14, stiffness: 100 },
            });

            const isActive = idx === currentActiveIdx;
            const pulse = isActive ? interpolate(Math.sin(frame * 0.15), [-1, 1], [0.95, 1.05]) : 1;

            return (
              <div
                key={stage.num}
                style={{
                  borderRadius: 20,
                  padding: '24px 28px',
                  backgroundColor: isActive ? 'rgba(15, 23, 42, 0.95)' : 'rgba(10, 15, 30, 0.8)',
                  border: isActive
                    ? `2px solid ${stage.color}`
                    : '1px solid rgba(255, 255, 255, 0.1)',
                  boxShadow: isActive
                    ? `0 20px 45px rgba(0, 0, 0, 0.8), 0 0 35px ${stage.color}40`
                    : '0 10px 25px rgba(0, 0, 0, 0.5)',
                  transform: `scale(${cardSpring * pulse}) translateY(${(1 - cardSpring) * 20}px)`,
                  opacity: cardSpring,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 12,
                  position: 'relative',
                  overflow: 'hidden',
                  transition: 'border 0.2s ease',
                }}
              >
                {/* Active glow dot */}
                {isActive && (
                  <div
                    style={{
                      position: 'absolute',
                      top: 16,
                      right: 16,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                    }}
                  >
                    <div
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        backgroundColor: stage.color,
                        boxShadow: `0 0 10px ${stage.color}`,
                      }}
                    />
                    <span
                      style={{
                        fontFamily: 'JetBrains Mono, monospace',
                        fontSize: 10,
                        fontWeight: 800,
                        color: stage.color,
                      }}
                    >
                      ACTIVE
                    </span>
                  </div>
                )}

                <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                  <div
                    style={{
                      width: 44,
                      height: 44,
                      borderRadius: 12,
                      backgroundColor: `${stage.color}20`,
                      border: `1px solid ${stage.color}40`,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: 22,
                    }}
                  >
                    {stage.icon}
                  </div>
                  <div>
                    <div
                      style={{
                        fontFamily: 'JetBrains Mono, monospace',
                        fontSize: 11,
                        fontWeight: 700,
                        color: stage.color,
                      }}
                    >
                      STAGE {stage.num}
                    </div>
                    <div
                      style={{
                        fontFamily: 'Inter, system-ui, sans-serif',
                        fontSize: 18,
                        fontWeight: 800,
                        color: '#ffffff',
                      }}
                    >
                      {stage.name}
                    </div>
                  </div>
                </div>

                <div
                  style={{
                    fontFamily: 'JetBrains Mono, monospace',
                    fontSize: 11,
                    color: '#94a3b8',
                    backgroundColor: 'rgba(255, 255, 255, 0.04)',
                    padding: '4px 10px',
                    borderRadius: 6,
                    width: 'fit-content',
                  }}
                >
                  {stage.tech}
                </div>

                <div
                  style={{
                    fontFamily: 'Inter, system-ui, sans-serif',
                    fontSize: 13,
                    lineHeight: 1.5,
                    color: '#cbd5e1',
                  }}
                >
                  {stage.desc}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <Captions subtitles={subtitles} />
    </div>
  );
};
