import React from 'react';
import { interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { Background } from '../components/Background';
import { Header } from '../components/Header';
import { Captions } from '../components/Captions';
import { SubtitleEntry } from '../types';

export const Scene1Hook: React.FC<{ subtitles: SubtitleEntry[] }> = ({ subtitles }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleSpring = spring({
    frame,
    fps,
    config: { damping: 14, stiffness: 80 },
  });

  const card1Spring = spring({
    frame: Math.max(0, frame - 15),
    fps,
    config: { damping: 12, stiffness: 90 },
  });

  const alertSpring = spring({
    frame: Math.max(0, frame - 60),
    fps,
    config: { damping: 10, stiffness: 120 },
  });

  const redAlertPulse = interpolate(Math.sin(frame * 0.15), [-1, 1], [0.85, 1.05]);

  return (
    <div style={{ position: 'relative', width: 1920, height: 1080, overflow: 'hidden' }}>
      <Background accentColor="#ef4444" />
      <Header sceneNumber="SCENE 01" sceneTag="The Concurrency Vulnerability" />

      {/* Main Content Area */}
      <div
        style={{
          position: 'absolute',
          top: 140,
          left: 100,
          right: 100,
          bottom: 120,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          gap: 36,
          zIndex: 10,
        }}
      >
        {/* Hero Title */}
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
              color: '#f87171',
              letterSpacing: '0.15em',
              textTransform: 'uppercase',
              marginBottom: 8,
            }}
          >
            CRITICAL FINANCIAL SYSTEM FAILURE
          </div>
          <h1
            style={{
              fontFamily: 'Inter, system-ui, sans-serif',
              fontSize: 56,
              fontWeight: 900,
              color: '#ffffff',
              letterSpacing: '-0.03em',
              margin: 0,
            }}
          >
            Why Standard Databases Fail Under Concurrency
          </h1>
        </div>

        {/* Comparison Grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: 40,
          }}
        >
          {/* Card 1: The Standard Database Race Condition */}
          <div
            style={{
              borderRadius: 24,
              padding: 36,
              backgroundColor: '#120d18',
              border: '2px solid rgba(239, 68, 68, 0.4)',
              boxShadow: '0 25px 60px rgba(0, 0, 0, 0.8), 0 0 40px rgba(239, 68, 68, 0.2)',
              transform: `scale(${card1Spring * redAlertPulse})`,
              opacity: card1Spring,
              display: 'flex',
              flexDirection: 'column',
              gap: 20,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ fontSize: 28 }}>❌</span>
                <div>
                  <h3
                    style={{
                      fontFamily: 'Inter, system-ui, sans-serif',
                      fontSize: 22,
                      fontWeight: 800,
                      color: '#fca5a5',
                      margin: 0,
                    }}
                  >
                    Naive Web Backend / RDBMS
                  </h3>
                  <span
                    style={{
                      fontFamily: 'JetBrains Mono, monospace',
                      fontSize: 12,
                      color: '#f87171',
                    }}
                  >
                    10 Simultaneous Debits vs $100 Initial Balance
                  </span>
                </div>
              </div>
              <span
                style={{
                  fontFamily: 'JetBrains Mono, monospace',
                  fontSize: 11,
                  fontWeight: 800,
                  padding: '4px 10px',
                  borderRadius: 6,
                  backgroundColor: 'rgba(239, 68, 68, 0.2)',
                  color: '#ef4444',
                  border: '1px solid rgba(239, 68, 68, 0.5)',
                }}
              >
                UNPROTECTED RACE
              </span>
            </div>

            {/* Code / Flow diagram */}
            <div
              style={{
                borderRadius: 14,
                backgroundColor: '#070409',
                padding: '16px 20px',
                fontFamily: 'JetBrains Mono, monospace',
                fontSize: 13,
                lineHeight: 1.6,
                color: '#e2e8f0',
                border: '1px solid rgba(239, 68, 68, 0.2)',
              }}
            >
              <div style={{ color: '#94a3b8' }}># Thread 1-5 read balance concurrently:</div>
              <div style={{ color: '#f87171' }}>Thread 1: SELECT balance (100) -&gt; 100 &gt; 50 -&gt; OK</div>
              <div style={{ color: '#f87171' }}>Thread 2: SELECT balance (100) -&gt; 100 &gt; 50 -&gt; OK</div>
              <div style={{ color: '#f87171' }}>Thread 3: SELECT balance (100) -&gt; 100 &gt; 50 -&gt; OK</div>
              <div style={{ color: '#f87171' }}>Thread 4: SELECT balance (100) -&gt; 100 &gt; 50 -&gt; OK</div>
              <div style={{ color: '#f87171' }}>Thread 5: SELECT balance (100) -&gt; 100 &gt; 50 -&gt; OK</div>
            </div>

            {/* Catastrophic Result Alert */}
            <div
              style={{
                borderRadius: 16,
                backgroundColor: 'rgba(239, 68, 68, 0.15)',
                border: '1px solid rgba(239, 68, 68, 0.4)',
                padding: '16px 20px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                transform: `scale(${alertSpring})`,
                opacity: alertSpring,
              }}
            >
              <div>
                <div
                  style={{
                    fontFamily: 'JetBrains Mono, monospace',
                    fontSize: 11,
                    color: '#fca5a5',
                    fontWeight: 700,
                  }}
                >
                  RESULTING LEDGER BALANCE
                </div>
                <div
                  style={{
                    fontFamily: 'JetBrains Mono, monospace',
                    fontSize: 32,
                    fontWeight: 900,
                    color: '#ef4444',
                    letterSpacing: '-0.02em',
                  }}
                >
                  -$150.0000
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <span
                  style={{
                    fontFamily: 'JetBrains Mono, monospace',
                    fontSize: 13,
                    fontWeight: 800,
                    color: '#f87171',
                  }}
                >
                  -$150,000+ Loss
                </span>
                <div style={{ fontSize: 11, color: '#94a3b8' }}>Silent Double Charges & Drift</div>
              </div>
            </div>
          </div>

          {/* Card 2: The PulseEngine Guarantee */}
          <div
            style={{
              borderRadius: 24,
              padding: 36,
              backgroundColor: '#0a1628',
              border: '2px solid rgba(16, 185, 129, 0.4)',
              boxShadow: '0 25px 60px rgba(0, 0, 0, 0.8), 0 0 40px rgba(16, 185, 129, 0.2)',
              transform: `scale(${card1Spring})`,
              opacity: card1Spring,
              display: 'flex',
              flexDirection: 'column',
              gap: 20,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ fontSize: 28 }}>🛡️</span>
                <div>
                  <h3
                    style={{
                      fontFamily: 'Inter, system-ui, sans-serif',
                      fontSize: 22,
                      fontWeight: 800,
                      color: '#86efac',
                      margin: 0,
                    }}
                  >
                    PulseEngine Distributed Engine
                  </h3>
                  <span
                    style={{
                      fontFamily: 'JetBrains Mono, monospace',
                      fontSize: 12,
                      color: '#34d399',
                    }}
                  >
                    Redlock Mutex + Double-Entry CAS Gate
                  </span>
                </div>
              </div>
              <span
                style={{
                  fontFamily: 'JetBrains Mono, monospace',
                  fontSize: 11,
                  fontWeight: 800,
                  padding: '4px 10px',
                  borderRadius: 6,
                  backgroundColor: 'rgba(16, 185, 129, 0.2)',
                  color: '#10b981',
                  border: '1px solid rgba(16, 185, 129, 0.5)',
                }}
              >
                PROVEN INVARIANT
              </span>
            </div>

            {/* Code / Flow diagram */}
            <div
              style={{
                borderRadius: 14,
                backgroundColor: '#040d1a',
                padding: '16px 20px',
                fontFamily: 'JetBrains Mono, monospace',
                fontSize: 13,
                lineHeight: 1.6,
                color: '#e2e8f0',
                border: '1px solid rgba(16, 185, 129, 0.2)',
              }}
            >
              <div style={{ color: '#94a3b8' }}># PulseEngine strictly serializes access:</div>
              <div style={{ color: '#34d399' }}>Thread 1: Acquire Mutex -&gt; Commit $50 -&gt; Bal: $50</div>
              <div style={{ color: '#34d399' }}>Thread 2: Acquire Mutex -&gt; Commit $50 -&gt; Bal: $0</div>
              <div style={{ color: '#fbbf24' }}>Thread 3: Check Balance ($0) -&gt; 422 REJECTED</div>
              <div style={{ color: '#fbbf24' }}>Thread 4: Check Balance ($0) -&gt; 422 REJECTED</div>
              <div style={{ color: '#fbbf24' }}>Thread 5: Check Balance ($0) -&gt; 422 REJECTED</div>
            </div>

            {/* Mathematical Guarantee Alert */}
            <div
              style={{
                borderRadius: 16,
                backgroundColor: 'rgba(16, 185, 129, 0.15)',
                border: '1px solid rgba(16, 185, 129, 0.4)',
                padding: '16px 20px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <div>
                <div
                  style={{
                    fontFamily: 'JetBrains Mono, monospace',
                    fontSize: 11,
                    color: '#86efac',
                    fontWeight: 700,
                  }}
                >
                  GUARANTEED ENDING BALANCE
                </div>
                <div
                  style={{
                    fontFamily: 'JetBrains Mono, monospace',
                    fontSize: 32,
                    fontWeight: 900,
                    color: '#10b981',
                    letterSpacing: '-0.02em',
                  }}
                >
                  $0.0000 USD
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <span
                  style={{
                    fontFamily: 'JetBrains Mono, monospace',
                    fontSize: 13,
                    fontWeight: 800,
                    color: '#34d399',
                  }}
                >
                  0.0000 Overdraft Drift
                </span>
                <div style={{ fontSize: 11, color: '#94a3b8' }}>Strict ACID Zero-Sum Invariant</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <Captions subtitles={subtitles} />
    </div>
  );
};
