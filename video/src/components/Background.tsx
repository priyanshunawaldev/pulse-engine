import React from 'react';
import { interpolate, useCurrentFrame } from 'remotion';

export const Background: React.FC<{ accentColor?: string }> = ({
  accentColor = '#3b82f6',
}) => {
  const frame = useCurrentFrame();
  const scanlineY = interpolate(frame % 150, [0, 150], [0, 1080]);
  const pulseOpacity = interpolate(
    Math.sin(frame * 0.05),
    [-1, 1],
    [0.2, 0.45]
  );

  return (
    <div
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: '#090d16',
        backgroundImage: `
          linear-gradient(to right, rgba(255, 255, 255, 0.04) 1px, transparent 1px),
          linear-gradient(to bottom, rgba(255, 255, 255, 0.04) 1px, transparent 1px)
        `,
        backgroundSize: '48px 48px',
        overflow: 'hidden',
        zIndex: 0,
      }}
    >
      {/* Top radial glow - pure hardware-accelerated gradient without CPU blur penalty */}
      <div
        style={{
          position: 'absolute',
          top: -200,
          left: '30%',
          width: 900,
          height: 700,
          borderRadius: '50%',
          background: `radial-gradient(ellipse at center, ${accentColor}44 0%, ${accentColor}18 40%, transparent 70%)`,
          opacity: pulseOpacity,
          pointerEvents: 'none',
        }}
      />

      {/* Bottom right subtle purple glow */}
      <div
        style={{
          position: 'absolute',
          bottom: -200,
          right: -100,
          width: 800,
          height: 600,
          borderRadius: '50%',
          background: `radial-gradient(ellipse at center, rgba(139, 92, 246, 0.35) 0%, rgba(139, 92, 246, 0.12) 40%, transparent 70%)`,
          opacity: pulseOpacity * 0.8,
          pointerEvents: 'none',
        }}
      />

      {/* Scanning laser beam effect */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: scanlineY,
          height: 2,
          background: `linear-gradient(90deg, transparent, ${accentColor}, transparent)`,
          opacity: 0.4,
          boxShadow: `0 0 15px ${accentColor}`,
          pointerEvents: 'none',
        }}
      />

      {/* Vignette */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          boxShadow: 'inset 0 0 180px rgba(0, 0, 0, 0.85)',
          pointerEvents: 'none',
        }}
      />
    </div>
  );
};
