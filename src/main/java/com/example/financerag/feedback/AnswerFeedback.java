package com.example.financerag.feedback;

import com.example.financerag.query.QueryHistory;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;

import java.time.LocalDateTime;

@Entity
@Table(name = "answer_feedbacks")
public class AnswerFeedback {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "query_history_id", nullable = false)
    private QueryHistory queryHistory;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private FeedbackRating rating;

    @Column(columnDefinition = "TEXT")
    private String comment;

    @Column(nullable = false)
    private LocalDateTime createdAt;

    protected AnswerFeedback() {
    }

    public AnswerFeedback(QueryHistory queryHistory, FeedbackRating rating, String comment) {
        this.queryHistory = queryHistory;
        this.rating = rating;
        this.comment = comment;
    }

    @PrePersist
    void prePersist() {
        this.createdAt = LocalDateTime.now();
    }

    public Long getId() {
        return id;
    }

    public QueryHistory getQueryHistory() {
        return queryHistory;
    }

    public FeedbackRating getRating() {
        return rating;
    }

    public String getComment() {
        return comment;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }
}
