import React from 'react';
import { interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';

interface TerminalLine {
  text: string;
  type?: 'command' | 'success' | 'info' | 'warn' | 'dim';
  delayFrames?: number;
}

interface TerminalWindowProps {
  title?: string;
  lines: TerminalLine[];
  width?: number | string;
}

export const TerminalWindow: React.FC<TerminalWindowProps> = ({
  title = 'bash - pulseengine-deploy',
  lines,
  width = '100%',
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const entrance = spring({
    frame,
    fps,
    config: { damping: 14, stiffness: 100 },
  });

  return (
    <div
      style={{
        width,
        borderRadius: 16,
        overflow: 'hidden',
        border: '1px solid rgba(255, 255, 255, 0.12)',
        backgroundColor: '#0a0f1d',
        boxShadow: '0 25px 60px rgba(0, 0, 0, 0.8), 0 0 40px rgba(34, 197, 94, 0.1)',
        transform: `scale(${entrance})`,
        opacity: entrance,
      }}
    >
      {/* Titlebar */}
      <div
        style={{
          height: 36,
          backgroundColor: '#131b2e',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          display: 'flex',
          alignItems: 'center',
          padding: '0 16px',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', gap: 8 }}>
          <div style={{ width: 11, height: 11, borderRadius: '50%', backgroundColor: '#ef4444' }} />
          <div style={{ width: 11, height: 11, borderRadius: '50%', backgroundColor: '#eab308' }} />
          <div style={{ width: 11, height: 11, borderRadius: '50%', backgroundColor: '#22c55e' }} />
        </div>
        <div
          style={{
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 12,
            color: '#94a3b8',
            fontWeight: 500,
          }}
        >
          {title}
        </div>
        <div style={{ width: 44 }} />
      </div>

      {/* Terminal Body */}
      <div
        style={{
          padding: '24px 28px',
          fontFamily: 'JetBrains Mono, Fira Code, monospace',
          fontSize: 15,
          lineHeight: 1.7,
        }}
      >
        {lines.map((line, idx) => {
          const delay = line.delayFrames ?? idx * 12;
          const isVisible = frame >= delay;
          if (!isVisible) return null;

          const lineProgress = spring({
            frame: frame - delay,
            fps,
            config: { damping: 12, stiffness: 150 },
          });

          let color = '#e2e8f0';
          let prefix = '';

          if (line.type === 'command') {
            color = '#38bdf8';
            prefix = '$ ';
          } else if (line.type === 'success') {
            color = '#34d399';
            prefix = '✔ ';
          } else if (line.type === 'warn') {
            color = '#fbbf24';
            prefix = '⚠ ';
          } else if (line.type === 'dim') {
            color = '#64748b';
          }

          return (
            <div
              key={idx}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                color,
                opacity: lineProgress,
                transform: `translateX(${(1 - lineProgress) * -10}px)`,
              }}
            >
              {prefix && (
                <span
                  style={{
                    color: line.type === 'command' ? '#22c55e' : color,
                    fontWeight: 700,
                  }}
                >
                  {prefix}
                </span>
              )}
              <span>{line.text}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
