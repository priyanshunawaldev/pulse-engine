import React from 'react';
import { Composition } from 'remotion';
import { PulseEngineMaster16x9 } from './scenes/PulseEngineMaster16x9';
import { PulseEngineShort9x16 } from './scenes/PulseEngineShort9x16';
import { Scene1Hook } from './scenes/Scene1Hook';
import { Scene2Architecture } from './scenes/Scene2Architecture';
import { Scene3LiveSandbox } from './scenes/Scene3LiveSandbox';
import { Scene4WarStories } from './scenes/Scene4WarStories';
import { Scene5DockerSpinUp } from './scenes/Scene5DockerSpinUp';
import { Scene6ScorecardOutro } from './scenes/Scene6ScorecardOutro';
import manifest from '../public/scenes_manifest.json';
import shortManifest from '../public/short_manifest.json';
import { ScenesManifest, ShortManifest } from './types';

const masterData = manifest as ScenesManifest;
const shortData = shortManifest as ShortManifest;

export const Root: React.FC = () => {
  return (
    <>
      <Composition
        id="PulseEngineMaster16x9"
        component={PulseEngineMaster16x9}
        durationInFrames={masterData.totalFrames}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="PulseEngineShort9x16"
        component={PulseEngineShort9x16}
        durationInFrames={shortData.durationFrames}
        fps={30}
        width={1080}
        height={1920}
      />
      <Composition
        id="Scene1"
        component={() => <Scene1Hook subtitles={masterData.scenes[0].subtitles} />}
        durationInFrames={masterData.scenes[0].durationFrames}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="Scene2"
        component={() => <Scene2Architecture subtitles={masterData.scenes[1].subtitles} />}
        durationInFrames={masterData.scenes[1].durationFrames}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="Scene3"
        component={() => <Scene3LiveSandbox subtitles={masterData.scenes[2].subtitles} />}
        durationInFrames={masterData.scenes[2].durationFrames}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="Scene4"
        component={() => <Scene4WarStories subtitles={masterData.scenes[3].subtitles} />}
        durationInFrames={masterData.scenes[3].durationFrames}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="Scene5"
        component={() => <Scene5DockerSpinUp subtitles={masterData.scenes[4].subtitles} />}
        durationInFrames={masterData.scenes[4].durationFrames}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="Scene6"
        component={() => <Scene6ScorecardOutro subtitles={masterData.scenes[5].subtitles} />}
        durationInFrames={masterData.scenes[5].durationFrames}
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};
