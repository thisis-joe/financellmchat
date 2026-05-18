package com.example.financerag.rag;

import java.util.List;

public record RagAnswerResponse(
        Long historyId,
        String question,
        String answer,
        List<Citation> citations,
        String status
) {

    public RagAnswerResponse withHistoryId(Long historyId) {
        return new RagAnswerResponse(historyId, question, answer, citations, status);
    }

    public record Citation(
            Long documentId,
            String title,
            String category,
            String institution,
            String productName,
            String productType,
            String source,
            String sourceUrl,
            double score,
            String snippet
    ) {
    }
}
