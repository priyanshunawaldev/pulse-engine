import React from 'react';
import { spring, useCurrentFrame, useVideoConfig } from 'remotion';

interface CodeBlockProps {
  filename: string;
  code: string;
  highlightLines?: number[];
  incidentBadge?: string;
  badgeType?: 'critical' | 'fix';
}

export const CodeBlock: React.FC<CodeBlockProps> = ({
  filename,
  code,
  highlightLines = [],
  incidentBadge,
  badgeType = 'fix',
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const entrance = spring({
    frame,
    fps,
    config: { damping: 14, stiffness: 90 },
  });

  const lines = code.trim().split('\n');

  return (
    <div
      style={{
        borderRadius: 14,
        overflow: 'hidden',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        backgroundColor: '#0c1322',
        boxShadow: '0 20px 40px rgba(0, 0, 0, 0.7)',
        transform: `scale(${entrance})`,
        opacity: entrance,
      }}
    >
      {/* Header bar */}
      <div
        style={{
          height: 38,
          backgroundColor: '#162035',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 16px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 13 }}>📄</span>
          <span
            style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 12,
              color: '#cbd5e1',
              fontWeight: 600,
            }}
          >
            {filename}
          </span>
        </div>

        {incidentBadge && (
          <span
            style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 10,
              fontWeight: 700,
              padding: '3px 8px',
              borderRadius: 6,
              backgroundColor: badgeType === 'critical' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)',
              color: badgeType === 'critical' ? '#f87171' : '#34d399',
              border: `1px solid ${badgeType === 'critical' ? 'rgba(239, 68, 68, 0.3)' : 'rgba(16, 185, 129, 0.3)'}`,
            }}
          >
            {incidentBadge}
          </span>
        )}
      </div>

      {/* Code contents */}
      <div
        style={{
          padding: '20px 24px',
          fontFamily: 'JetBrains Mono, Fira Code, monospace',
          fontSize: 14,
          lineHeight: 1.65,
          color: '#e2e8f0',
        }}
      >
        {lines.map((lineText, idx) => {
          const lineNum = idx + 1;
          const isHighlighted = highlightLines.includes(lineNum);
          return (
            <div
              key={idx}
              style={{
                display: 'flex',
                gap: 16,
                backgroundColor: isHighlighted ? 'rgba(56, 189, 248, 0.12)' : 'transparent',
                borderRadius: 4,
                padding: '1px 6px',
                borderLeft: isHighlighted ? '3px solid #38bdf8' : '3px solid transparent',
              }}
            >
              <span
                style={{
                  color: isHighlighted ? '#38bdf8' : '#475569',
                  userSelect: 'none',
                  width: 24,
                  textAlign: 'right',
                  fontSize: 12,
                }}
              >
                {lineNum}
              </span>
              <span
                style={{
                  color: isHighlighted ? '#ffffff' : '#94a3b8',
                  fontWeight: isHighlighted ? 600 : 400,
                }}
              >
                {lineText}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
