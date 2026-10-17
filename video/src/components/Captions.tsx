import React from 'react';
import { interpolate, useCurrentFrame, useVideoConfig } from 'remotion';
import { SubtitleEntry } from '../types';

interface CaptionsProps {
  subtitles: SubtitleEntry[];
  sceneStartOffsetSeconds?: number;
}

export const Captions: React.FC<CaptionsProps> = ({
  subtitles,
  sceneStartOffsetSeconds = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentTime = frame / fps + sceneStartOffsetSeconds;

  // Find active subtitle
  const activeSub = subtitles.find(
    (sub) => currentTime >= sub.start && currentTime <= sub.end + 0.2
  );

  if (!activeSub) {
    return null;
  }

  // Calculate word progress
  const duration = Math.max(0.1, activeSub.end - activeSub.start);
  const progress = Math.min(1, Math.max(0, (currentTime - activeSub.start) / duration));
  const words = activeSub.text.split(' ');
  const activeWordIdx = Math.floor(progress * words.length);

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 40,
        left: 80,
        right: 80,
        display: 'flex',
        justifyContent: 'center',
        zIndex: 60,
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          maxWidth: 1200,
          background: 'rgba(10, 15, 30, 0.95)',
          border: '1px solid rgba(255, 255, 255, 0.15)',
          borderRadius: 24,
          padding: '16px 32px',
          boxShadow: '0 20px 40px rgba(0, 0, 0, 0.6), 0 0 30px rgba(59, 130, 246, 0.15)',
          textAlign: 'center',
        }}
      >
        <span
          style={{
            fontFamily: 'Inter, system-ui, sans-serif',
            fontSize: 22,
            fontWeight: 700,
            lineHeight: 1.4,
            letterSpacing: '-0.01em',
          }}
        >
          {words.map((word, i) => {
            const isSpoken = i <= activeWordIdx;
            const isCurrent = i === activeWordIdx;
            return (
              <span
                key={i}
                style={{
                  display: 'inline-block',
                  marginRight: 8,
                  color: isCurrent
                    ? '#38bdf8'
                    : isSpoken
                    ? '#ffffff'
                    : 'rgba(255, 255, 255, 0.4)',
                  transform: isCurrent ? 'scale(1.08)' : 'scale(1.0)',
                  textShadow: isCurrent
                    ? '0 0 16px rgba(56, 189, 248, 0.9), 0 0 30px rgba(56, 189, 248, 0.4)'
                    : 'none',
                  transition: 'all 0.1s ease',
                  fontWeight: isCurrent ? 800 : isSpoken ? 700 : 500,
                }}
              >
                {word}
              </span>
            );
          })}
        </span>
      </div>
    </div>
  );
};
