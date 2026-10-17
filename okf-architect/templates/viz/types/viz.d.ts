/**
 * University Knowledge Cosmos & Cornell Study Portal Type Definitions
 * Ambient global declarations for pure browser runtime and tsc typecheck.
 */

type NodeId = string & { readonly __brand: unique symbol };
type TimestampSeconds = number & { readonly __brand: unique symbol };

type OKFNodeType =
  | "concept"
  | "note"
  | "worked_solution"
  | "topic"
  | "lab"
  | "video"
  | "pdf"
  | "summary"
  | "course"
  | string;

type OKFLinkType =
  | "dependency"
  | "related"
  | "hierarchical"
  | "cross-week"
  | string;

type ViewMode =
  | "constellation"
  | "semantic"
  | "sunburst"
  | "kanban";

type AcademicDrawerTab =
  | "summary"
  | "cornell"
  | "solution"
  | "slides"
  | "anki";

interface CornellCue {
  readonly cue: string;
  readonly timestamp?: string;
  readonly seconds?: number;
  readonly note: string;
  readonly tags?: readonly string[];
}

interface CornellSection {
  readonly heading: string;
  readonly content: string;
}

interface OKFNode {
  readonly id: string;
  readonly name?: string;
  readonly label?: string;
  readonly cleanTitle?: string;
  readonly type: OKFNodeType;
  readonly val?: number;
  readonly cluster?: number;
  readonly week?: string;
  readonly level?: string;
  readonly course?: string;
  readonly summary?: string;
  readonly tags?: readonly string[];
  readonly cues?: readonly CornellCue[];
  readonly sections?: readonly CornellSection[];
  readonly cornell_path?: string;
  readonly cornellPath?: string;
  readonly cornellUrl?: string;
  readonly hasCornell?: boolean;
  readonly pdf_path?: string;
  readonly pdfPath?: string;
  readonly video_url?: string;
  readonly videoUrl?: string;
  readonly cornellCards?: readonly any[];
  readonly status?: string;
  readonly module?: string;
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
  fx?: number | null;
  fy?: number | null;
  sunburstX?: number;
  sunburstY?: number;
  [key: string]: any;
}

interface OKFLink {
  readonly source: string | OKFNode | any;
  readonly target: string | OKFNode | any;
  readonly type?: OKFLinkType | string;
  readonly value?: number;
  [key: string]: any;
}

type VideoSource =
  | {
      readonly type: "zoom";
      readonly src: string;
      readonly passcode?: string;
      readonly fallbackSrc?: string;
      readonly title?: string;
      readonly label?: string;
      readonly seconds?: number;
      readonly timestamp?: number;
      readonly time_str?: string;
      [key: string]: any;
    }
  | {
      readonly type: "mp4";
      readonly src: string;
      readonly fallbackSrc?: string;
      readonly title?: string;
      readonly label?: string;
      readonly seconds?: number;
      readonly timestamp?: number;
      readonly time_str?: string;
      [key: string]: any;
    }
  | {
      readonly type: "youtube";
      readonly src: string;
      readonly title?: string;
      readonly label?: string;
      readonly seconds?: number;
      readonly timestamp?: number;
      readonly time_str?: string;
      [key: string]: any;
    };

interface WorkedSolutionEntry {
  readonly title: string;
  readonly type: "zoom" | "mp4" | "youtube";
  readonly videoSrc: string;
  readonly passcode?: string;
  readonly fallbackSrc?: string;
  readonly cues?: readonly CornellCue[];
}

interface AnkiCard {
  readonly id: string;
  readonly cue: string;
  readonly note: string;
  readonly folder?: string;
  readonly tags?: readonly string[];
  ease?: number;
  interval?: number;
  reps?: number;
  due?: number;
  [key: string]: any;
}

interface KanbanItem {
  readonly id: string;
  readonly text: string;
  column: "todo" | "in_progress" | "done";
  readonly week?: string;
  readonly sourceNodeId?: string;
}

interface DigUpResult {
  readonly type: "cue" | "slide" | "concept" | "solution";
  readonly title: string;
  readonly label: string;
  readonly snippet: string;
  readonly timestamp?: string;
  readonly seconds?: number;
  readonly nodeId?: string;
  readonly video?: VideoSource;
}

declare var d3: any;
declare var katex: any;
declare var renderMathInElement: (el: HTMLElement, opts?: any) => void;
declare var marked: { parse: (src: string) => string };

interface Window {
  d3: any;
  katex: any;
  renderMathInElement: (el: HTMLElement, opts?: any) => void;
  marked: { parse: (src: string) => string };

  RAW_NODES: OKFNode[];
  RAW_LINKS: OKFLink[];
  WORKED_SOLUTIONS_DB: Record<string, WorkedSolutionEntry>;
  graphNodes: OKFNode[];
  graphSimulation: any;
  cornellNoteCatalog?: any[];

  setViewMode: (mode: ViewMode) => void;
  openCornellModal: (path: string, title?: string) => void;
  closeCornellModal: () => void;
  openAnkiModal: (folderFilter?: string) => void;
  closeAnkiModal: () => void;
  openDigUpModal: () => void;
  closeDigUpModal: () => void;
  openPdfModal: (path: string, title?: string) => void;
  closePdfModal: () => void;
  openVideoClip: (data: VideoSource | any) => void;
  openVideoClipFromStr: (jsonStr: string) => void;
  showZoomCard: (zoomUrl: string, passcode?: string, timeStr?: string, title?: string) => void;
  launchZoomWithPasscode: () => void;
  closeVideoDrawer: () => void;
  toggleVideoDrawerMinimize: () => void;
  selectNodeById: (id: string) => void;
  toggleCornellFilter: () => void;
  __graph: any;
}
