package com.example.financerag.rag;

import java.util.List;

public record RagApiRequest(String question, String sessionId, List<RagChatMessage> history) {
}
