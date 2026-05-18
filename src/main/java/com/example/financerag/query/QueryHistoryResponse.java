package com.example.financerag.query;

import java.time.LocalDateTime;

public record QueryHistoryResponse(
        Long id,
        String question,
        String answer,
        String citationsJson,
        String status,
        LocalDateTime createdAt
) {

    public static QueryHistoryResponse from(QueryHistory history) {
        return new QueryHistoryResponse(
                history.getId(),
                history.getQuestion(),
                history.getAnswer(),
                history.getCitationsJson(),
                history.getStatus(),
                history.getCreatedAt()
        );
    }
}
