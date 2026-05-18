package com.example.financerag.query;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;

import java.time.LocalDateTime;

@Entity
@Table(name = "query_histories")
public class QueryHistory {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, columnDefinition = "TEXT")
    private String question;

    @Column(nullable = false, columnDefinition = "TEXT")
    private String answer;

    @Column(nullable = false, columnDefinition = "TEXT")
    private String citationsJson;

    @Column(nullable = false, length = 40)
    private String status;

    @Column(nullable = false)
    private LocalDateTime createdAt;

    protected QueryHistory() {
    }

    public QueryHistory(String question, String answer, String citationsJson, String status) {
        this.question = question;
        this.answer = answer;
        this.citationsJson = citationsJson;
        this.status = status;
    }

    @PrePersist
    void prePersist() {
        this.createdAt = LocalDateTime.now();
    }

    public Long getId() {
        return id;
    }

    public String getQuestion() {
        return question;
    }

    public String getAnswer() {
        return answer;
    }

    public String getCitationsJson() {
        return citationsJson;
    }

    public String getStatus() {
        return status;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }
}
