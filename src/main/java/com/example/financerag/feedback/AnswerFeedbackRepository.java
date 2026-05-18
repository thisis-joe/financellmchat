package com.example.financerag.feedback;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface AnswerFeedbackRepository extends JpaRepository<AnswerFeedback, Long> {

    List<AnswerFeedback> findTop20ByOrderByCreatedAtDesc();
}
