import React from 'react';
import { interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';

interface BrowserFrameProps {
  url?: string;
  children: React.ReactNode;
  width?: number | string;
  height?: number | string;
  scale?: number;
}

export const BrowserFrame: React.FC<BrowserFrameProps> = ({
  url = 'https://pulseengine.internal/sandbox',
  children,
  width = '100%',
  height = '100%',
  scale = 1,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const entrance = spring({
    frame,
    fps,
    config: { damping: 15, stiffness: 90 },
  });

  return (
    <div
      style={{
        width,
        height,
        transform: `scale(${entrance * scale})`,
        opacity: entrance,
        borderRadius: 16,
        overflow: 'hidden',
        border: '1px solid rgba(255, 255, 255, 0.12)',
        backgroundColor: '#0f172a',
        boxShadow: '0 25px 60px -15px rgba(0, 0, 0, 0.8), 0 0 35px rgba(56, 189, 248, 0.15)',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Titlebar */}
      <div
        style={{
          height: 38,
          backgroundColor: '#1e293b',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          display: 'flex',
          alignItems: 'center',
          padding: '0 16px',
          justifyContent: 'space-between',
        }}
      >
        {/* Traffic lights */}
        <div style={{ display: 'flex', gap: 8 }}>
          <div
            style={{
              width: 12,
              height: 12,
              borderRadius: '50%',
              backgroundColor: '#ef4444',
            }}
          />
          <div
            style={{
              width: 12,
              height: 12,
              borderRadius: '50%',
              backgroundColor: '#eab308',
            }}
          />
          <div
            style={{
              width: 12,
              height: 12,
              borderRadius: '50%',
              backgroundColor: '#22c55e',
            }}
          />
        </div>

        {/* URL Pill */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '4px 20px',
            borderRadius: 8,
            backgroundColor: 'rgba(15, 23, 42, 0.7)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 11,
            color: '#94a3b8',
          }}
        >
          <span style={{ color: '#22c55e' }}>🔒</span>
          <span>{url}</span>
        </div>

        {/* Empty placeholder for balance */}
        <div style={{ width: 48 }} />
      </div>

      {/* Viewport Content */}
      <div
        style={{
          flex: 1,
          position: 'relative',
          overflow: 'hidden',
          backgroundColor: '#020617',
        }}
      >
        {children}
      </div>
    </div>
  );
};
