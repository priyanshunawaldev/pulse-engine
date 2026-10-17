import React from 'react';
import { interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';

interface HeaderProps {
  sceneTag: string;
  sceneNumber: string;
}

export const Header: React.FC<HeaderProps> = ({ sceneTag, sceneNumber }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const entrance = spring({
    frame,
    fps,
    config: { damping: 14, stiffness: 100 },
  });

  const pulse = interpolate(Math.sin(frame * 0.1), [-1, 1], [0.6, 1]);

  return (
    <div
      style={{
        position: 'absolute',
        top: 40,
        left: 60,
        right: 60,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        zIndex: 50,
        transform: `translateY(${(1 - entrance) * -30}px)`,
        opacity: entrance,
      }}
    >
      {/* Brand logo & title */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <div
          style={{
            width: 44,
            height: 44,
            borderRadius: 12,
            background: 'linear-gradient(135deg, #2563eb, #7c3aed)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 22,
            boxShadow: '0 0 20px rgba(59, 130, 246, 0.5)',
          }}
        >
          ⚡
        </div>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span
              style={{
                fontFamily: 'Inter, system-ui, sans-serif',
                fontSize: 24,
                fontWeight: 900,
                color: '#ffffff',
                letterSpacing: '-0.02em',
              }}
            >
              PulseEngine
            </span>
            <span
              style={{
                fontSize: 11,
                fontFamily: 'JetBrains Mono, monospace',
                padding: '3px 8px',
                borderRadius: 6,
                background: 'rgba(56, 189, 248, 0.15)',
                color: '#38bdf8',
                border: '1px solid rgba(56, 189, 248, 0.3)',
                fontWeight: 700,
              }}
            >
              DISTRIBUTED LEDGER
            </span>
          </div>
          <div
            style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 12,
              color: '#94a3b8',
              letterSpacing: '0.05em',
            }}
          >
            HIGH-THROUGHPUT EVENT INGESTION & CAS SETTLEMENT
          </div>
        </div>
      </div>

      {/* Scene indicator & badges */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '8px 16px',
            borderRadius: 30,
            background: 'rgba(15, 23, 42, 0.94)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
          }}
        >
          <div
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              backgroundColor: '#10b981',
              boxShadow: `0 0 10px rgba(16, 185, 129, ${pulse})`,
            }}
          />
          <span
            style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 12,
              color: '#cbd5e1',
              fontWeight: 600,
            }}
          >
            {sceneNumber} • {sceneTag.toUpperCase()}
          </span>
        </div>
      </div>
    </div>
  );
};
