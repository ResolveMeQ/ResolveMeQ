/**
 * TypeScript Type Definitions for ResolveMeQ AI Chat API
 * 
 * Usage:
 * import { ChatMessage, Conversation, SendMessageRequest, SendMessageResponse } from './types/chat';
 */

// ============================================================================
// Message Types
// ============================================================================

export type SenderType = 'user' | 'ai' | 'system';

export type MessageType = 
  | 'text'              // Regular text message
  | 'steps'             // Step-by-step instructions
  | 'question'          // AI asking for clarification
  | 'solution'          // Proposed solution
  | 'file_request'      // AI needs files/screenshots
  | 'similar_tickets'   // Showing related tickets
  | 'kb_article';       // Knowledge base article reference

export type FeedbackRating = 'helpful' | 'not_helpful';

// ============================================================================
// Core Models
// ============================================================================

export interface ChatMessage {
  id: string;
  sender_type: SenderType;
  message_type: MessageType;
  text: string;
  confidence?: number;  // 0.0 - 1.0, only present for AI messages
  metadata?: MessageMetadata;
  was_helpful?: boolean | null;
  feedback_comment?: string | null;
  created_at: string;  // ISO 8601 datetime
}

export interface MessageMetadata {
  steps?: string[];
  suggested_actions?: string[];
  quick_replies?: QuickReply[];
  attachments?: Attachment[];
  similar_tickets?: SimilarTicket[];
  kb_articles?: KBArticle[];
  [key: string]: any;  // Allow additional fields
}

export interface QuickReply {
  label: string;
  value: string;
  icon?: string;
}

export interface Conversation {
  id: string;
  ticket: number;
  user?: number;
  messages: ChatMessage[];
  message_count: number;
  is_active: boolean;
  resolved: boolean;
  resolution_applied: boolean;
  summary?: string;
  created_at: string;
  updated_at: string;
}

export interface QuickReplySuggestion {
  id: string;
  category: string;
  label: string;
  message_text: string;
  priority: number;
  is_active: boolean;
}

// ============================================================================
// API Request/Response Types
// ============================================================================

export interface SendMessageRequest {
  message: string;
  conversation_id?: string;  // Optional, omit to start new conversation
}

export interface SendMessageResponse {
  conversation_id: string;
  user_message: ChatMessage;
  ai_message: ChatMessage;
}

export interface ConversationHistoryResponse {
  id: string;
  ticket: number;
  messages: ChatMessage[];
  message_count: number;
  created_at: string;
  resolved: boolean;
}

export interface SubmitFeedbackRequest {
  rating: FeedbackRating;
  comment?: string;
}

export interface SubmitFeedbackResponse {
  message: string;
  message_id: string;
  was_helpful: boolean;
}

export interface SuggestionsResponse {
  suggestions: QuickReplySuggestion[];
  ticket_id: number;
  category?: string;
}

// ============================================================================
// Additional Types
// ============================================================================

export interface Attachment {
  id: string;
  filename: string;
  url: string;
  content_type: string;
  size: number;
}

export interface SimilarTicket {
  ticket_id: number;
  issue_type: string;
  resolution: string;
  similarity_score: number;
}

export interface KBArticle {
  id: string;
  title: string;
  url: string;
  relevance: number;
}

// ============================================================================
// Confidence Levels
// ============================================================================

export enum ConfidenceLevel {
  HIGH = 'high',    // >= 0.8
  MEDIUM = 'medium', // >= 0.6
  LOW = 'low'       // < 0.6
}

export function getConfidenceLevel(confidence: number): ConfidenceLevel {
  if (confidence >= 0.8) return ConfidenceLevel.HIGH;
  if (confidence >= 0.6) return ConfidenceLevel.MEDIUM;
  return ConfidenceLevel.LOW;
}

export function getConfidenceColor(confidence: number): string {
  const level = getConfidenceLevel(confidence);
  switch (level) {
    case ConfidenceLevel.HIGH:
      return 'green';
    case ConfidenceLevel.MEDIUM:
      return 'yellow';
    case ConfidenceLevel.LOW:
      return 'red';
  }
}

export function getConfidenceLabel(confidence: number): string {
  const level = getConfidenceLevel(confidence);
  const percent = Math.round(confidence * 100);
  switch (level) {
    case ConfidenceLevel.HIGH:
      return `High Confidence (${percent}%)`;
    case ConfidenceLevel.MEDIUM:
      return `Medium Confidence (${percent}%)`;
    case ConfidenceLevel.LOW:
      return `Low Confidence (${percent}%)`;
  }
}

// ============================================================================
// API Client Interface
// ============================================================================

export interface ChatAPIClient {
  /**
   * Send a chat message and receive AI response
   */
  sendMessage(ticketId: number, request: SendMessageRequest): Promise<SendMessageResponse>;

  /**
   * Get conversation history for a ticket
   */
  getHistory(ticketId: number): Promise<ConversationHistoryResponse>;

  /**
   * Submit feedback for an AI message
   */
  submitFeedback(ticketId: number, messageId: string, request: SubmitFeedbackRequest): Promise<SubmitFeedbackResponse>;

  /**
   * Get quick reply suggestions
   */
  getSuggestions(ticketId: number, category?: string): Promise<SuggestionsResponse>;
}

// ============================================================================
// Example Implementation
// ============================================================================

export class ChatAPIClientImpl implements ChatAPIClient {
  constructor(private baseURL: string, private getAuthToken: () => string) {}

  async sendMessage(ticketId: number, request: SendMessageRequest): Promise<SendMessageResponse> {
    const response = await fetch(`${this.baseURL}/api/tickets/${ticketId}/chat/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.getAuthToken()}`,
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`Failed to send message: ${response.statusText}`);
    }

    return response.json();
  }

  async getHistory(ticketId: number): Promise<ConversationHistoryResponse> {
    const response = await fetch(`${this.baseURL}/api/tickets/${ticketId}/chat/history/`, {
      headers: {
        'Authorization': `Bearer ${this.getAuthToken()}`,
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to get history: ${response.statusText}`);
    }

    return response.json();
  }

  async submitFeedback(
    ticketId: number,
    messageId: string,
    request: SubmitFeedbackRequest
  ): Promise<SubmitFeedbackResponse> {
    const response = await fetch(
      `${this.baseURL}/api/tickets/${ticketId}/chat/${messageId}/feedback/`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.getAuthToken()}`,
        },
        body: JSON.stringify(request),
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to submit feedback: ${response.statusText}`);
    }

    return response.json();
  }

  async getSuggestions(ticketId: number, category?: string): Promise<SuggestionsResponse> {
    const url = new URL(`${this.baseURL}/api/tickets/${ticketId}/chat/suggestions/`);
    if (category) {
      url.searchParams.append('category', category);
    }

    const response = await fetch(url.toString(), {
      headers: {
        'Authorization': `Bearer ${this.getAuthToken()}`,
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to get suggestions: ${response.statusText}`);
    }

    return response.json();
  }
}

// ============================================================================
// React Hooks (Optional)
// ============================================================================

/**
 * Example React hook for chat functionality
 * 
 * Usage:
 * const { messages, sendMessage, isTyping, submitFeedback } = useChat(ticketId);
 */
export interface UseChatReturn {
  messages: ChatMessage[];
  conversationId: string | null;
  isTyping: boolean;
  isLoading: boolean;
  error: Error | null;
  sendMessage: (text: string) => Promise<void>;
  submitFeedback: (messageId: string, helpful: boolean, comment?: string) => Promise<void>;
  loadHistory: () => Promise<void>;
}
