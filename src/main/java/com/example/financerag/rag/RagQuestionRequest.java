package com.example.financerag.rag;

import jakarta.validation.constraints.NotBlank;

import java.util.List;

public class RagQuestionRequest {

    @NotBlank
    private String question;

    private String sessionId;

    private List<RagChatMessage> history = List.of();

    public String getQuestion() {
        return question;
    }

    public void setQuestion(String question) {
        this.question = question;
    }

    public String getSessionId() {
        return sessionId;
    }

    public void setSessionId(String sessionId) {
        this.sessionId = sessionId;
    }

    public List<RagChatMessage> getHistory() {
        return history == null ? List.of() : history;
    }

    public void setHistory(List<RagChatMessage> history) {
        this.history = history == null ? List.of() : history;
    }
}
