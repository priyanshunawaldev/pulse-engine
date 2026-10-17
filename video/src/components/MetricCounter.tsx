import React from 'react';
import { interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';

interface MetricCardProps {
  label: string;
  value: string;
  detail: string;
  icon?: string;
  accentColor?: string;
  delayFrames?: number;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  detail,
  icon = '📈',
  accentColor = '#3b82f6',
  delayFrames = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const entrance = spring({
    frame: Math.max(0, frame - delayFrames),
    fps,
    config: { damping: 12, stiffness: 100 },
  });

  return (
    <div
      style={{
        borderRadius: 20,
        padding: '28px 32px',
        backgroundColor: '#0c1324',
        border: `1px solid ${accentColor}33`,
        boxShadow: `0 20px 45px rgba(0, 0, 0, 0.7), 0 0 30px ${accentColor}18`,
        transform: `scale(${entrance}) translateY(${(1 - entrance) * 20}px)`,
        opacity: entrance,
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Subtle background glow */}
      <div
        style={{
          position: 'absolute',
          top: -40,
          right: -40,
          width: 140,
          height: 140,
          borderRadius: '50%',
          background: `radial-gradient(circle, ${accentColor}25 0%, transparent 70%)`,
          pointerEvents: 'none',
        }}
      />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span
          style={{
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 12,
            fontWeight: 700,
            color: '#94a3b8',
            letterSpacing: '0.05em',
            textTransform: 'uppercase',
          }}
        >
          {label}
        </span>
        <span style={{ fontSize: 20 }}>{icon}</span>
      </div>

      <div
        style={{
          fontFamily: 'Inter, system-ui, sans-serif',
          fontSize: 48,
          fontWeight: 900,
          color: accentColor,
          letterSpacing: '-0.03em',
          textShadow: `0 0 25px ${accentColor}66`,
          lineHeight: 1.1,
        }}
      >
        {value}
      </div>

      <div
        style={{
          fontFamily: 'Inter, system-ui, sans-serif',
          fontSize: 13,
          color: '#cbd5e1',
          lineHeight: 1.4,
        }}
      >
        {detail}
      </div>
    </div>
  );
};
