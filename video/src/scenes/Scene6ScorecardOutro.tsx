import React from 'react';
import { interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { Background } from '../components/Background';
import { Header } from '../components/Header';
import { MetricCard } from '../components/MetricCounter';
import { Captions } from '../components/Captions';
import { SubtitleEntry } from '../types';

export const Scene6ScorecardOutro: React.FC<{ subtitles: SubtitleEntry[] }> = ({ subtitles }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleSpring = spring({
    frame,
    fps,
    config: { damping: 14, stiffness: 80 },
  });

  const ctaSpring = spring({
    frame: Math.max(0, frame - 100),
    fps,
    config: { damping: 12, stiffness: 90 },
  });

  return (
    <div style={{ position: 'relative', width: 1920, height: 1080, overflow: 'hidden' }}>
      <Background accentColor="#10b981" />
      <Header sceneNumber="SCENE 06" sceneTag="Staff Verification & Outro" />

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
          gap: 32,
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
              color: '#34d399',
              letterSpacing: '0.15em',
              textTransform: 'uppercase',
              marginBottom: 4,
            }}
          >
            VERIFIED BENCHMARKS & AUDIT READINESS
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
            Staff-Level Verification Scorecard
          </h1>
        </div>

        {/* 4 Metric Cards */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: 24,
          }}
        >
          <MetricCard
            label="Automated Tests"
            value="39 / 39"
            detail="100% Pytest pass rate across async race tests, mutexes, & webhooks."
            icon="🧪"
            accentColor="#10b981"
            delayFrames={10}
          />

          <MetricCard
            label="Code Coverage"
            value="92.1%"
            detail="Branch-level coverage enforcing zero uncovered financial paths."
            icon="📊"
            accentColor="#38bdf8"
            delayFrames={25}
          />

          <MetricCard
            label="p95 Latency"
            value="< 34ms"
            detail="Sub-40ms response times sustained under 1,000+ requests/second."
            icon="⚡"
            accentColor="#a855f7"
            delayFrames={40}
          />

          <MetricCard
            label="Postmortems Solved"
            value="14 / 14"
            detail="Documented edge cases: deadlocks, fake OCC, and lock leak fixes."
            icon="🛡️"
            accentColor="#f59e0b"
            delayFrames={55}
          />
        </div>

        {/* Call-To-Action Banner */}
        <div
          style={{
            borderRadius: 20,
            padding: '24px 36px',
            backgroundColor: 'rgba(15, 23, 42, 0.95)',
            border: '2px solid rgba(56, 189, 248, 0.4)',
            boxShadow: '0 20px 45px rgba(0, 0, 0, 0.8), 0 0 35px rgba(56, 189, 248, 0.2)',
            transform: `scale(${ctaSpring})`,
            opacity: ctaSpring,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
            <div
              style={{
                width: 52,
                height: 52,
                borderRadius: 14,
                backgroundColor: 'rgba(56, 189, 248, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 26,
              }}
            >
              💻
            </div>
            <div>
              <div
                style={{
                  fontFamily: 'Inter, system-ui, sans-serif',
                  fontSize: 20,
                  fontWeight: 900,
                  color: '#ffffff',
                }}
              >
                PulseEngine is Open Source & Ready For Production
              </div>
              <div
                style={{
                  fontFamily: 'JetBrains Mono, monospace',
                  fontSize: 13,
                  color: '#94a3b8',
                }}
              >
                Inspect the postmortems, run stress tests, and explore the architecture on GitHub
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: 12 }}>
            <div
              style={{
                padding: '10px 20px',
                borderRadius: 10,
                backgroundColor: 'rgba(16, 185, 129, 0.15)',
                border: '1px solid rgba(16, 185, 129, 0.3)',
                color: '#34d399',
                fontFamily: 'JetBrains Mono, monospace',
                fontSize: 12,
                fontWeight: 700,
              }}
            >
              SOX 404 & PCI-DSS READY
            </div>
            <div
              style={{
                padding: '10px 24px',
                borderRadius: 10,
                backgroundColor: '#2563eb',
                color: '#ffffff',
                fontFamily: 'Inter, system-ui, sans-serif',
                fontSize: 13,
                fontWeight: 800,
                boxShadow: '0 0 20px rgba(37, 99, 235, 0.6)',
              }}
            >
              EXPLORE REPO →
            </div>
          </div>
        </div>
      </div>

      <Captions subtitles={subtitles} />
    </div>
  );
};
