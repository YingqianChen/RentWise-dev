/**
 * TypeScript types for RentWise API
 */

// ============== Auth ==============

export interface User {
  id: string;
  email: string;
  created_at: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
}

// ============== Project ==============

export interface Project {
  id: string;
  user_id: string;
  title: string;
  status: "active" | "archived" | "completed";
  max_budget: number | null;
  preferred_districts: string[];
  must_have: string[];
  deal_breakers: string[];
  move_in_target: string | null;
  notes: string | null;
  commute_enabled: boolean;
  commute_destination_label: string | null;
  commute_destination_query: string | null;
  commute_mode: "transit" | "driving" | "walking" | null;
  max_commute_minutes: number | null;
  commute_destination_lat: number | null;
  commute_destination_lng: number | null;
  created_at: string;
  updated_at: string;
}

export interface CreateProjectRequest {
  title: string;
  max_budget?: number;
  preferred_districts?: string[];
  must_have?: string[];
  deal_breakers?: string[];
  move_in_target?: string;
  notes?: string;
  commute_destination_label?: string;
  commute_destination_query?: string;
  commute_mode?: "transit" | "driving" | "walking";
  max_commute_minutes?: number;
}

export interface UpdateProjectRequest {
  title?: string;
  status?: "active" | "archived" | "completed";
  max_budget?: number;
  preferred_districts?: string[];
  must_have?: string[];
  deal_breakers?: string[];
  move_in_target?: string;
  notes?: string;
  commute_destination_label?: string;
  commute_destination_query?: string;
  commute_mode?: "transit" | "driving" | "walking";
  max_commute_minutes?: number;
}

// ============== Candidate ==============

export interface ExtractedInfo {
  candidate_id: string;
  monthly_rent: string | null;
  management_fee_amount: string | null;
  management_fee_included: boolean | null;
  rates_amount: string | null;
  rates_included: boolean | null;
  deposit: string | null;
  agent_fee: string | null;
  lease_term: string | null;
  move_in_date: string | null;
  repair_responsibility: string | null;
  district: string | null;
  furnished: string | null;
  size_sqft: string | null;
  bedrooms: string | null;
  suspected_sdu: boolean | null;
  sdu_detection_reason: string | null;
  address_text: string | null;
  building_name: string | null;
  nearest_station: string | null;
  location_confidence: "high" | "medium" | "low" | "unknown";
  location_source: string;
  decision_signals: DecisionSignal[];
  raw_facts: string[];
  ocr_texts: string[];
}

export interface DecisionSignal {
  key: string;
  category: string;
  label: string;
  source: string;
  evidence: string;
  note: string | null;
}

export interface CandidateSourceAsset {
  id: string;
  storage_provider: string;
  storage_key: string;
  original_filename: string;
  content_type: string | null;
  file_size: number | null;
  ocr_status: "pending" | "succeeded" | "failed" | "skipped";
  ocr_text: string | null;
  created_at: string;
  updated_at: string;
}

export interface CostAssessment {
  candidate_id: string;
  known_monthly_cost: number | null;
  monthly_cost_confidence: "high" | "medium" | "low";
  monthly_cost_missing_items: string[];
  move_in_cost_known_part: number | null;
  move_in_cost_confidence: "high" | "medium" | "low";
  cost_risk_flag: "none" | "possible_additional_cost" | "hidden_cost_risk" | "over_budget";
  summary: string;
}

export interface ClauseAssessment {
  candidate_id: string;
  repair_responsibility_level: "clear" | "supported_but_unconfirmed" | "unclear" | "tenant_heavy" | "unknown";
  lease_term_level: "standard" | "rigid" | "unstable" | "unknown";
  move_in_date_level: "fit" | "mismatch" | "uncertain" | "unknown";
  clause_confidence: "high" | "medium" | "low";
  clause_risk_flag: "none" | "needs_confirmation" | "high_risk";
  summary: string;
}

export interface CandidateAssessment {
  candidate_id: string;
  top_level_recommendation: "shortlist_recommendation" | "not_ready" | "likely_reject";
  potential_value_level: "high" | "medium" | "low";
  completeness_level: "high" | "medium" | "low";
  critical_uncertainty_level: "high" | "medium" | "low";
  decision_risk_level: "high" | "medium" | "low";
  information_gain_level: "high" | "medium" | "low";
  recommendation_confidence: "high" | "medium" | "low";
  next_best_action: "verify_cost" | "verify_clause" | "schedule_viewing" | "keep_warm" | "reject";
  status: "new" | "needs_info" | "follow_up" | "high_risk_pending" | "recommended_reject" | "shortlisted";
  labels: string[];
  summary: string;
}

export interface BenchmarkEvidence {
  status: "not_applicable" | "no_district" | "no_benchmark_record" | "available";
  district: string | null;
  source_period: string | null;
  median_monthly_rent: number | null;
  median_monthly_rent_per_sqm: number | null;
  record_note: "normal" | "fewer_than_10_records" | "no_records" | null;
  disclaimer: string | null;
  fit_note: string | null;
}

export type CommuteSegmentMode =
  | "walking"
  | "subway"
  | "bus"
  | "minibus"
  | "rail"
  | "airport_express"
  | "taxi";

export interface CommuteSegment {
  mode: CommuteSegmentMode | string;
  line_name: string | null;
  from_station: string | null;
  to_station: string | null;
  duration_minutes: number | null;
  distance_meters: number | null;
}

export interface CommuteEvidence {
  status: "not_configured" | "insufficient_candidate_location" | "ready" | "failed";
  estimated_minutes: number | null;
  mode: string | null;
  route_summary: string | null;
  origin_station: string | null;
  destination_station: string | null;
  segments: CommuteSegment[] | null;
  destination_label: string | null;
  confidence_note: string | null;
}

export interface Candidate {
  id: string;
  project_id: string;
  name: string;
  source_type: "manual_text" | "chat_log" | "image_upload" | "mixed";
  raw_listing_text: string | null;
  raw_chat_text: string | null;
  raw_note_text: string | null;
  combined_text: string | null;
  status: string;
  processing_stage: "queued" | "running_ocr" | "extracting" | "completed" | "failed" | null;
  processing_error: string | null;
  user_decision: "undecided" | "shortlisted" | "rejected";
  created_at: string;
  updated_at: string;
  extracted_info: ExtractedInfo | null;
  cost_assessment: CostAssessment | null;
  clause_assessment: ClauseAssessment | null;
  candidate_assessment: CandidateAssessment | null;
  benchmark: BenchmarkEvidence | null;
  commute_evidence: CommuteEvidence | null;
  source_assets: CandidateSourceAsset[];
}

export interface CandidateContactPlan {
  contact_goal: string;
  questions: string[];
  message_draft: string;
}

export interface ImportCandidateRequest {
  name?: string;
  source_type?: "manual_text" | "chat_log" | "image_upload" | "mixed";
  raw_listing_text?: string;
  raw_chat_text?: string;
  raw_note_text?: string;
  uploaded_images?: File[];
}

export interface UpdateCandidateRequest {
  name?: string;
  raw_listing_text?: string;
  raw_chat_text?: string;
  raw_note_text?: string;
  address_text?: string;
  building_name?: string;
  nearest_station?: string;
}

// ============== Dashboard ==============

export interface CandidateStats {
  total: number;
  new: number;
  needs_info: number;
  follow_up: number;
  high_risk_pending: number;
  recommended_reject: number;
  shortlisted: number;
  rejected: number;
}

export interface PriorityCandidate {
  id: string;
  name: string;
  status: string;
  potential_value_level: string;
  completeness_level: string;
  next_best_action: string;
  monthly_rent: string | null;
  district: string | null;
  reason: string;
  priority_score: number;
}

export interface InvestigationItem {
  id: string;
  candidate_id: string | null;
  category: "cost" | "clause" | "timing" | "match";
  title: string;
  question: string;
  priority: "high" | "medium" | "low";
  status: "open" | "resolved" | "dismissed";
}

export interface SuggestedComparePreview {
  candidate_ids: string[];
  candidate_names: string[];
  headline: string;
  summary: string;
  action_prompt: string;
}

export interface Dashboard {
  project_id: string;
  stats: CandidateStats;
  current_advice: string;
  priority_candidates: PriorityCandidate[];
  open_investigation_items: InvestigationItem[];
  compare_preview: SuggestedComparePreview | null;
  generated_at: string;
}

// ============== Investigation ==============

export interface InvestigationResponse {
  project_id: string;
  current_advice: string;
  priority_candidates: PriorityCandidate[];
  open_items: InvestigationItem[];
  generated_at: string;
}

// ============== Comparison ==============

export interface CompareSummary {
  headline: string;
  summary: string;
  confidence_note: string;
}

export interface CompareAgentBriefing {
  current_take: string;
  why_now: string;
  what_could_change: string;
  today_s_move: string;
  confidence_note: string;
}

export interface CompareCandidateCard {
  candidate_id: string;
  name: string;
  compare_group: "best_current_option" | "viable_alternative" | "not_ready" | "likely_drop";
  top_recommendation: "shortlist_recommendation" | "not_ready" | "likely_reject";
  decision_explanation: string;
  main_tradeoff: string;
  open_blocker: string | null;
  next_action: "verify_cost" | "verify_clause" | "schedule_viewing" | "keep_warm" | "reject";
  monthly_rent: string | null;
  district: string | null;
  status: string;
  benchmark: BenchmarkEvidence | null;
  commute_evidence: CommuteEvidence | null;
}

export interface CompareDecisionGroups {
  best_current_option: CompareCandidateCard | null;
  viable_alternatives: CompareCandidateCard[];
  not_ready_for_fair_comparison: CompareCandidateCard[];
  likely_drop: CompareCandidateCard[];
}

export interface CompareDifference {
  category: string;
  title: string;
  summary: string;
}

export interface CompareActionTarget {
  candidate_id: string;
  name: string;
  reason: string;
}

export interface CompareRecommendedActions {
  contact_first: CompareActionTarget | null;
  questions_to_ask: string[];
  viewing_candidate: CompareActionTarget | null;
  deprioritize: CompareActionTarget[];
}

export interface ComparisonResponse {
  project_id: string;
  selected_count: number;
  summary: CompareSummary;
  agent_briefing: CompareAgentBriefing;
  groups: CompareDecisionGroups;
  key_differences: CompareDifference[];
  recommended_next_actions: CompareRecommendedActions;
  generated_at: string;
}
