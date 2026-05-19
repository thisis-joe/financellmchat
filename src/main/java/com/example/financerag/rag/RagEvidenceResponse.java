package com.example.financerag.rag;

import java.time.LocalDateTime;
import java.util.List;

public record RagEvidenceResponse(
        Long historyId,
        String question,
        String status,
        String summary,
        List<Evidence> evidences,
        LocalDateTime createdAt
) {

    public record Evidence(
            int rank,
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
