import React from 'react';
import { interpolate, spring, staticFile, useCurrentFrame, useVideoConfig, Img } from 'remotion';
import { Background } from '../components/Background';
import { Header } from '../components/Header';
import { BrowserFrame } from '../components/BrowserFrame';
import { Captions } from '../components/Captions';
import { SubtitleEntry } from '../types';

export const Scene3LiveSandbox: React.FC<{ subtitles: SubtitleEntry[] }> = ({ subtitles }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleSpring = spring({
    frame,
    fps,
    config: { damping: 14, stiffness: 80 },
  });

  const badgeSpring = spring({
    frame: Math.max(0, frame - 30),
    fps,
    config: { damping: 10, stiffness: 120 },
  });

  // Dynamic screenshot sequence based on frame (total duration: ~1098 frames)
  let currentScreenshot = 'screenshots/01_initial_sim.png';
  let statusBadge = {
    title: 'SANDBOX READY',
    desc: 'Alice: $100.0000 | Bob: $50.0000 • Invariant Checked',
    color: '#38bdf8',
    icon: '💡',
  };

  if (frame > 180 && frame <= 420) {
    currentScreenshot = 'screenshots/02_transfer_done.png';
    statusBadge = {
      title: 'TRANSFER COMMITTED',
      desc: 'Alice: $75.0000 | Bob: $75.0000 • Double-Entry Sum == 0',
      color: '#3b82f6',
      icon: '💸',
    };
  } else if (frame > 420 && frame <= 780) {
    currentScreenshot = 'screenshots/03_race_concurrency.png';
    statusBadge = {
      title: 'CONCURRENCY RACE PREVENTED',
      desc: 'Alice: $0.0000 • 5 Passed, 5 Rejected (422) • Zero Overdraft',
      color: '#10b981',
      icon: '🛡️',
    };
  } else if (frame > 780 && frame <= 950) {
    currentScreenshot = 'screenshots/04_idempotency_replay.png';
    statusBadge = {
      title: 'IDEMPOTENCY VERIFIED',
      desc: 'Replayed Key • Returned 200 From Cache • 0 Ledger Mutation',
      color: '#f59e0b',
      icon: '🔁',
    };
  } else if (frame > 950) {
    currentScreenshot = 'screenshots/05_audit_reconcile.png';
    statusBadge = {
      title: 'NIGHTLY AUDIT PASSED',
      desc: 'Balance == Initial + Sum(LedgerEntries) • Zero Drift Check',
      color: '#10b981',
      icon: '⚖️',
    };
  }

  // Subtle dynamic pan
  const zoomScale = interpolate(frame % 300, [0, 150, 300], [1.0, 1.03, 1.0], {
    extrapolateRight: 'clamp',
  });

  return (
    <div style={{ position: 'relative', width: 1920, height: 1080, overflow: 'hidden' }}>
      <Background accentColor="#10b981" />
      <Header sceneNumber="SCENE 03" sceneTag="Live Adversarial Stress Test" />

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
          alignItems: 'center',
          gap: 20,
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
            REAL-TIME BROWSER SIMULATOR
          </div>
          <h1
            style={{
              fontFamily: 'Inter, system-ui, sans-serif',
              fontSize: 44,
              fontWeight: 900,
              color: '#ffffff',
              letterSpacing: '-0.03em',
              margin: 0,
            }}
          >
            10-Thread Concurrency Race Test & Idempotency
          </h1>
        </div>

        {/* Browser Mockup Window */}
        <div style={{ width: 1380, height: 620, position: 'relative' }}>
          <BrowserFrame url="https://pulseengine.internal/sandbox">
            <Img
              src={staticFile(currentScreenshot)}
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'cover',
                objectPosition: 'top center',
                transform: `scale(${zoomScale})`,
                transition: 'transform 0.5s ease',
              }}
            />
          </BrowserFrame>

          {/* Floating Live Verification Badge */}
          <div
            style={{
              position: 'absolute',
              bottom: 24,
              right: 24,
              backgroundColor: 'rgba(10, 15, 30, 0.95)',
              border: `2px solid ${statusBadge.color}`,
              borderRadius: 16,
              padding: '16px 24px',
              boxShadow: `0 15px 35px rgba(0, 0, 0, 0.8), 0 0 25px ${statusBadge.color}40`,
              transform: `scale(${badgeSpring})`,
              opacity: badgeSpring,
              display: 'flex',
              flexDirection: 'column',
              gap: 4,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 18 }}>{statusBadge.icon}</span>
              <span
                style={{
                  fontFamily: 'JetBrains Mono, monospace',
                  fontSize: 12,
                  fontWeight: 800,
                  color: statusBadge.color,
                }}
              >
                {statusBadge.title}
              </span>
            </div>
            <div
              style={{
                fontFamily: 'Inter, system-ui, sans-serif',
                fontSize: 14,
                fontWeight: 800,
                color: '#ffffff',
              }}
            >
              {statusBadge.desc}
            </div>
          </div>
        </div>
      </div>

      <Captions subtitles={subtitles} />
    </div>
  );
};
