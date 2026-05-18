package com.example.financerag.feedback;

import com.example.financerag.common.ResourceNotFoundException;
import com.example.financerag.query.QueryHistory;
import com.example.financerag.query.QueryHistoryRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class FeedbackService {

    private final AnswerFeedbackRepository feedbackRepository;
    private final QueryHistoryRepository historyRepository;

    public FeedbackService(AnswerFeedbackRepository feedbackRepository, QueryHistoryRepository historyRepository) {
        this.feedbackRepository = feedbackRepository;
        this.historyRepository = historyRepository;
    }

    @Transactional
    public FeedbackResponse create(Long historyId, FeedbackRequest request) {
        QueryHistory history = historyRepository.findById(historyId)
                .orElseThrow(() -> new ResourceNotFoundException("질문 이력을 찾을 수 없습니다. historyId=" + historyId));
        AnswerFeedback feedback = feedbackRepository.save(new AnswerFeedback(
                history,
                request.getRating(),
                normalizeComment(request.getComment())
        ));
        return FeedbackResponse.from(feedback);
    }

    @Transactional(readOnly = true)
    public List<FeedbackResponse> recentFeedbacks() {
        return feedbackRepository.findTop20ByOrderByCreatedAtDesc()
                .stream()
                .map(FeedbackResponse::from)
                .toList();
    }

    private String normalizeComment(String comment) {
        if (comment == null || comment.isBlank()) {
            return null;
        }
        return comment.trim();
    }
}
