import React from 'react';
import { Audio, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig, Img } from 'remotion';
import { Background } from '../components/Background';
import { BrowserFrame } from '../components/BrowserFrame';
import shortManifest from '../../public/short_manifest.json';
import { ShortManifest } from '../types';

const data = shortManifest as ShortManifest;

export const PulseEngineShort9x16: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const currentTime = frame / fps;

  // Active subtitle
  const activeSub = data.subtitles.find(
    (sub) => currentTime >= sub.start && currentTime <= sub.end + 0.2
  );

  const words = activeSub ? activeSub.text.split(' ') : [];
  const duration = activeSub ? Math.max(0.1, activeSub.end - activeSub.start) : 1;
  const progress = activeSub ? Math.min(1, Math.max(0, (currentTime - activeSub.start) / duration)) : 0;
  const activeWordIdx = Math.floor(progress * words.length);

  const titleSpring = spring({
    frame,
    fps,
    config: { damping: 14, stiffness: 80 },
  });

  const cardSpring = spring({
    frame: Math.max(0, frame - 20),
    fps,
    config: { damping: 12, stiffness: 90 },
  });

  // Dynamic screenshot for short
  let currentScreenshot = 'screenshots/01_initial_sim.png';
  if (frame > 250 && frame <= 500) {
    currentScreenshot = 'screenshots/02_transfer_done.png';
  } else if (frame > 500 && frame <= 1100) {
    currentScreenshot = 'screenshots/03_race_concurrency.png';
  } else if (frame > 1100 && frame <= 1350) {
    currentScreenshot = 'screenshots/04_idempotency_replay.png';
  } else if (frame > 1350) {
    currentScreenshot = 'screenshots/09_tab_benchmarks.png';
  }

  return (
    <div
      style={{
        position: 'relative',
        width: 1080,
        height: 1920,
        backgroundColor: '#070b14',
        overflow: 'hidden',
      }}
    >
      <Background accentColor="#3b82f6" />

      {/* Voiceover & Ambient Music */}
      <Audio src={staticFile('audio/short_master.mp3')} volume={1.0} />
      <Audio src={staticFile('audio/ambient_bgm.mp3')} volume={0.10} loop />

      {/* Vertical Container */}
      <div
        style={{
          position: 'absolute',
          top: 80,
          left: 50,
          right: 50,
          bottom: 80,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'space-between',
          zIndex: 20,
        }}
      >
        {/* Top Header */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 16,
            transform: `translateY(${(1 - titleSpring) * -30}px)`,
            opacity: titleSpring,
            textAlign: 'center',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '8px 20px',
              borderRadius: 30,
              backgroundColor: 'rgba(15, 23, 42, 0.9)',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              boxShadow: '0 0 25px rgba(56, 189, 248, 0.2)',
            }}
          >
            <span style={{ fontSize: 20 }}>⚡</span>
            <span
              style={{
                fontFamily: 'JetBrains Mono, monospace',
                fontSize: 14,
                fontWeight: 800,
                color: '#38bdf8',
                letterSpacing: '0.1em',
              }}
            >
              PULSEENGINE
            </span>
          </div>

          <h1
            style={{
              fontFamily: 'Inter, system-ui, sans-serif',
              fontSize: 48,
              fontWeight: 900,
              color: '#ffffff',
              letterSpacing: '-0.03em',
              lineHeight: 1.15,
              margin: 0,
            }}
          >
            What Happens Under 10 Concurrent Flash-Sale Debits?
          </h1>

          <div
            style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 14,
              color: '#94a3b8',
            }}
          >
            Distributed Ledger • Redlock Mutex • Zero Overdraft
          </div>
        </div>

        {/* Browser Mockup Window */}
        <div
          style={{
            width: '100%',
            height: 680,
            transform: `scale(${cardSpring})`,
            opacity: cardSpring,
          }}
        >
          <BrowserFrame url="https://pulseengine.internal/sandbox">
            <Img
              src={staticFile(currentScreenshot)}
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'cover',
                objectPosition: 'top center',
              }}
            />
          </BrowserFrame>
        </div>

        {/* 4 Feature Badges Grid */}
        <div
          style={{
            width: '100%',
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: 16,
          }}
        >
          <div
            style={{
              borderRadius: 16,
              padding: '16px 20px',
              backgroundColor: 'rgba(15, 23, 42, 0.9)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              display: 'flex',
              alignItems: 'center',
              gap: 12,
            }}
          >
            <span style={{ fontSize: 24 }}>🛡️</span>
            <div>
              <div style={{ fontFamily: 'Inter, system-ui', fontSize: 18, fontWeight: 900, color: '#34d399' }}>
                $0.0000
              </div>
              <div style={{ fontSize: 11, color: '#94a3b8' }}>Zero Overdraft Guarantee</div>
            </div>
          </div>

          <div
            style={{
              borderRadius: 16,
              padding: '16px 20px',
              backgroundColor: 'rgba(15, 23, 42, 0.9)',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              display: 'flex',
              alignItems: 'center',
              gap: 12,
            }}
          >
            <span style={{ fontSize: 24 }}>🧪</span>
            <div>
              <div style={{ fontFamily: 'Inter, system-ui', fontSize: 18, fontWeight: 900, color: '#38bdf8' }}>
                39 / 39 Tests
              </div>
              <div style={{ fontSize: 11, color: '#94a3b8' }}>100% Pytest Passing</div>
            </div>
          </div>

          <div
            style={{
              borderRadius: 16,
              padding: '16px 20px',
              backgroundColor: 'rgba(15, 23, 42, 0.9)',
              border: '1px solid rgba(168, 85, 247, 0.3)',
              display: 'flex',
              alignItems: 'center',
              gap: 12,
            }}
          >
            <span style={{ fontSize: 24 }}>⚡</span>
            <div>
              <div style={{ fontFamily: 'Inter, system-ui', fontSize: 18, fontWeight: 900, color: '#c084fc' }}>
                &lt; 34ms p95
              </div>
              <div style={{ fontSize: 11, color: '#94a3b8' }}>@ 1,000+ req/sec</div>
            </div>
          </div>

          <div
            style={{
              borderRadius: 16,
              padding: '16px 20px',
              backgroundColor: 'rgba(15, 23, 42, 0.9)',
              border: '1px solid rgba(245, 158, 11, 0.3)',
              display: 'flex',
              alignItems: 'center',
              gap: 12,
            }}
          >
            <span style={{ fontSize: 24 }}>🔒</span>
            <div>
              <div style={{ fontFamily: 'Inter, system-ui', fontSize: 18, fontWeight: 900, color: '#fbbf24' }}>
                Redlock Mutex
              </div>
              <div style={{ fontSize: 11, color: '#94a3b8' }}>UUID Ordered Locking</div>
            </div>
          </div>
        </div>

        {/* Mobile Big Captions Box */}
        <div
          style={{
            width: '100%',
            minHeight: 180,
            borderRadius: 24,
            padding: '24px 32px',
            backgroundColor: 'rgba(10, 15, 30, 0.95)',
            border: '2px solid rgba(56, 189, 248, 0.3)',
            boxShadow: '0 20px 50px rgba(0, 0, 0, 0.8), 0 0 35px rgba(56, 189, 248, 0.2)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            textAlign: 'center',
          }}
        >
          {activeSub ? (
            <div
              style={{
                fontFamily: 'Inter, system-ui, sans-serif',
                fontSize: 32,
                fontWeight: 800,
                lineHeight: 1.35,
              }}
            >
              {words.map((w, i) => {
                const isCurrent = i === activeWordIdx;
                const isSpoken = i <= activeWordIdx;
                return (
                  <span
                    key={i}
                    style={{
                      display: 'inline-block',
                      marginRight: 10,
                      color: isCurrent
                        ? '#38bdf8'
                        : isSpoken
                        ? '#ffffff'
                        : 'rgba(255, 255, 255, 0.35)',
                      transform: isCurrent ? 'scale(1.12)' : 'scale(1.0)',
                      textShadow: isCurrent
                        ? '0 0 20px rgba(56, 189, 248, 1), 0 0 35px rgba(56, 189, 248, 0.6)'
                        : 'none',
                      transition: 'all 0.1s ease',
                      fontWeight: isCurrent ? 900 : 700,
                    }}
                  >
                    {w}
                  </span>
                );
              })}
            </div>
          ) : (
            <div
              style={{
                fontFamily: 'JetBrains Mono, monospace',
                fontSize: 18,
                color: '#64748b',
              }}
            >
              PulseEngine Distributed Architecture
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
