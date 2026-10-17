import React from 'react';
import { spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { Background } from '../components/Background';
import { Header } from '../components/Header';
import { TerminalWindow } from '../components/TerminalWindow';
import { Captions } from '../components/Captions';
import { SubtitleEntry } from '../types';

const SERVICES = [
  { name: 'pulseengine-api', port: '8000:8000', tech: 'FastAPI / Python 3.12', status: 'HEALTHY' },
  { name: 'pulseengine-db', port: '5432:5432', tech: 'PostgreSQL 16 Alpine', status: 'HEALTHY' },
  { name: 'pulseengine-redis', port: '6379:6379', tech: 'Redis 7 Alpine', status: 'HEALTHY' },
  { name: 'pulseengine-worker', port: 'Internal', tech: 'Celery Distributed Task', status: 'ONLINE' },
  { name: 'pulseengine-beat', port: 'Cron', tech: 'Celery Beat Nightly Audit', status: 'ONLINE' },
];

export const Scene5DockerSpinUp: React.FC<{ subtitles: SubtitleEntry[] }> = ({ subtitles }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleSpring = spring({
    frame,
    fps,
    config: { damping: 14, stiffness: 80 },
  });

  const terminalLines = [
    { text: 'docker compose up --build -d', type: 'command' as const, delayFrames: 5 },
    { text: '[+] Building 0.0s (0/0)', type: 'dim' as const, delayFrames: 25 },
    { text: '[+] Running 5/5', type: 'info' as const, delayFrames: 45 },
    { text: 'Network pulseengine_default Created', type: 'success' as const, delayFrames: 60 },
    { text: 'Container pulseengine-redis-1 Started (healthy)', type: 'success' as const, delayFrames: 80 },
    { text: 'Container pulseengine-db-1 Started (healthy: 5432)', type: 'success' as const, delayFrames: 100 },
    { text: 'Container pulseengine-api-1 Started (healthy: 8000)', type: 'success' as const, delayFrames: 125 },
    { text: 'Container pulseengine-worker-1 Started (Celery consumer online)', type: 'success' as const, delayFrames: 150 },
    { text: 'Container pulseengine-beat-1 Started (Scheduler active)', type: 'success' as const, delayFrames: 175 },
    { text: 'All 5 cluster containers healthy. Zero-trust pipeline active.', type: 'info' as const, delayFrames: 210 },
    { text: 'GET /api/v1/metrics/health -> 200 OK (Postgres: UP, Redis: UP)', type: 'success' as const, delayFrames: 260 },
    { text: 'PulseEngine distributed cluster ready for production traffic.', type: 'info' as const, delayFrames: 310 },
  ];

  return (
    <div style={{ position: 'relative', width: 1920, height: 1080, overflow: 'hidden' }}>
      <Background accentColor="#38bdf8" />
      <Header sceneNumber="SCENE 05" sceneTag="Infrastructure & Spin-Up" />

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
              color: '#38bdf8',
              letterSpacing: '0.15em',
              textTransform: 'uppercase',
              marginBottom: 4,
            }}
          >
            CONTAINERIZED ZERO-TO-ONE REPRODUCIBILITY
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
            Spin-Up With A Single Docker Command
          </h1>
        </div>

        {/* Two-Column Layout: Terminal + Service Grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1.2fr 1fr',
            gap: 36,
            alignItems: 'center',
          }}
        >
          {/* Terminal Window */}
          <TerminalWindow
            title="bash - terminal@pulseengine"
            lines={terminalLines}
          />

          {/* Microservices Cluster Cards */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {SERVICES.map((svc, idx) => {
              const cardSpring = spring({
                frame: Math.max(0, frame - 80 - idx * 15),
                fps,
                config: { damping: 14, stiffness: 100 },
              });

              return (
                <div
                  key={svc.name}
                  style={{
                    borderRadius: 14,
                    padding: '14px 20px',
                    backgroundColor: 'rgba(15, 23, 42, 0.9)',
                    border: '1px solid rgba(56, 189, 248, 0.2)',
                    boxShadow: '0 8px 20px rgba(0, 0, 0, 0.5)',
                    transform: `scale(${cardSpring})`,
                    opacity: cardSpring,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div
                      style={{
                        width: 10,
                        height: 10,
                        borderRadius: '50%',
                        backgroundColor: '#10b981',
                        boxShadow: '0 0 10px #10b981',
                      }}
                    />
                    <div>
                      <div
                        style={{
                          fontFamily: 'JetBrains Mono, monospace',
                          fontSize: 14,
                          fontWeight: 700,
                          color: '#ffffff',
                        }}
                      >
                        {svc.name}
                      </div>
                      <div style={{ fontSize: 11, color: '#94a3b8' }}>{svc.tech}</div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span
                      style={{
                        fontFamily: 'JetBrains Mono, monospace',
                        fontSize: 11,
                        color: '#64748b',
                      }}
                    >
                      {svc.port}
                    </span>
                    <span
                      style={{
                        fontFamily: 'JetBrains Mono, monospace',
                        fontSize: 10,
                        fontWeight: 800,
                        backgroundColor: 'rgba(16, 185, 129, 0.15)',
                        color: '#34d399',
                        border: '1px solid rgba(16, 185, 129, 0.3)',
                        padding: '3px 8px',
                        borderRadius: 6,
                      }}
                    >
                      {svc.status}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <Captions subtitles={subtitles} />
    </div>
  );
};
