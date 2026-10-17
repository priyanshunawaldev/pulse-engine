export interface SubtitleEntry {
  start: number; // in seconds
  end: number;   // in seconds
  text: string;
}

export interface SceneMeta {
  id: string;
  title: string;
  audio: string;
  duration: number;
  durationFrames: number;
  startOffset: number;
  startOffsetFrames: number;
  subtitles: SubtitleEntry[];
  fullText: string;
}

export interface ScenesManifest {
  totalDuration: number;
  totalFrames: number;
  fps: number;
  scenes: SceneMeta[];
}

export interface ShortManifest {
  id: string;
  title: string;
  audio: string;
  duration: number;
  durationFrames: number;
  fps: number;
  subtitles: SubtitleEntry[];
  fullText: string;
}
