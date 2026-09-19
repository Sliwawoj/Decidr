export interface Decision {
  id: string;
  gmail_message_id: string;
  gmail_thread_id: string;
  rfc_message_id: string | null;
  sender_name: string;
  sender_email: string;
  subject: string;
  received_at: string;
  original_body: string;
  summary: string;
  request_text: string;
  decision_type: "purchase" | "invoice" | "schedule" | "routine" | "other";
  amount: number | null;
  currency: string | null;
  deadline: string | null;
  conditions: string[];
  missing_fields: string[];
  risk_flags: string[];
  safety_reasons: string[];
  confidence: number;
  classification: "needs_reply" | "needs_review" | "skip";
  status:
    | "analyzed"
    | "pending"
    | "skipped"
    | "draft_ready"
    | "sent"
    | "demo_completed";
  user_choice: "approve" | "reject" | null;
  draft: string | null;
  is_demo: boolean;
  created_at: string;
  updated_at: string;
  sent_at: string | null;
  send_attempted_at: string | null;
  send_error: string | null;
  version: number;
}
export interface AppStatus {
  mode: "demo" | "live";
  authenticated: boolean;
  gmail: { configured: boolean; connected: boolean; email: string | null };
  llm: { configured: boolean; model: string };
  push: { configured: boolean; public_key: string | null };
  last_sync_at: string | null;
  last_sync_error: string | null;
}
