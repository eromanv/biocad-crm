/** Canonical plan/task contract shared with the FastAPI backend. */

export interface Task {
  id: string;
  name: string;
  description: string;
  assignee: string;
  duration_days: number;
  predecessor_ids: string[];
  start: string;
  finish: string;
  is_critical: boolean;
}

export interface Plan {
  project_start: string;
  tasks: Task[];
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  /** When true, render as an error bubble (failed chat / API). */
  isError?: boolean;
}
