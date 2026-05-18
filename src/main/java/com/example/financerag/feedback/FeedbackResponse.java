package com.example.financerag.feedback;

import java.time.LocalDateTime;

public record FeedbackResponse(
        Long id,
        Long historyId,
        FeedbackRating rating,
        String comment,
        LocalDateTime createdAt
) {

    public static FeedbackResponse from(AnswerFeedback feedback) {
        return new FeedbackResponse(
                feedback.getId(),
                feedback.getQueryHistory().getId(),
                feedback.getRating(),
                feedback.getComment(),
                feedback.getCreatedAt()
        );
    }
}
