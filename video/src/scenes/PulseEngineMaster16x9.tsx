import React from 'react';
import { Audio, Sequence, staticFile } from 'remotion';
import { Scene1Hook } from './Scene1Hook';
import { Scene2Architecture } from './Scene2Architecture';
import { Scene3LiveSandbox } from './Scene3LiveSandbox';
import { Scene4WarStories } from './Scene4WarStories';
import { Scene5DockerSpinUp } from './Scene5DockerSpinUp';
import { Scene6ScorecardOutro } from './Scene6ScorecardOutro';
import manifest from '../../public/scenes_manifest.json';
import { ScenesManifest } from '../types';

const data = manifest as ScenesManifest;

export const PulseEngineMaster16x9: React.FC = () => {
  const scene1 = data.scenes[0];
  const scene2 = data.scenes[1];
  const scene3 = data.scenes[2];
  const scene4 = data.scenes[3];
  const scene5 = data.scenes[4];
  const scene6 = data.scenes[5];

  return (
    <div style={{ position: 'relative', width: 1920, height: 1080, backgroundColor: '#090d16' }}>
      {/* Ambient background music bed */}
      <Audio
        src={staticFile('audio/ambient_bgm.mp3')}
        volume={0.10}
        loop
      />

      {/* Scene 1: The $150,000 Overdraft Horror Story */}
      <Sequence from={scene1.startOffsetFrames} durationInFrames={scene1.durationFrames}>
        <Audio src={staticFile(scene1.audio)} volume={1.0} />
        <Scene1Hook subtitles={scene1.subtitles} />
      </Sequence>

      {/* Scene 2: The 6-Stage Defense In Depth */}
      <Sequence from={scene2.startOffsetFrames} durationInFrames={scene2.durationFrames}>
        <Audio src={staticFile(scene2.audio)} volume={1.0} />
        <Scene2Architecture subtitles={scene2.subtitles} />
      </Sequence>

      {/* Scene 3: Live Sandbox Battle-Testing */}
      <Sequence from={scene3.startOffsetFrames} durationInFrames={scene3.durationFrames}>
        <Audio src={staticFile(scene3.audio)} volume={1.0} />
        <Scene3LiveSandbox subtitles={scene3.subtitles} />
      </Sequence>

      {/* Scene 4: Engineering War Stories & Under The Hood */}
      <Sequence from={scene4.startOffsetFrames} durationInFrames={scene4.durationFrames}>
        <Audio src={staticFile(scene4.audio)} volume={1.0} />
        <Scene4WarStories subtitles={scene4.subtitles} />
      </Sequence>

      {/* Scene 5: Spin-Up & Zero-To-One Deployment */}
      <Sequence from={scene5.startOffsetFrames} durationInFrames={scene5.durationFrames}>
        <Audio src={staticFile(scene5.audio)} volume={1.0} />
        <Scene5DockerSpinUp subtitles={scene5.subtitles} />
      </Sequence>

      {/* Scene 6: Staff Benchmark Scorecard & Outro */}
      <Sequence from={scene6.startOffsetFrames} durationInFrames={scene6.durationFrames}>
        <Audio src={staticFile(scene6.audio)} volume={1.0} />
        <Scene6ScorecardOutro subtitles={scene6.subtitles} />
      </Sequence>
    </div>
  );
};
