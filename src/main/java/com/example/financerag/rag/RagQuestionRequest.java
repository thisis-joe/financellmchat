package com.example.financerag.rag;

import jakarta.validation.constraints.NotBlank;

public class RagQuestionRequest {

    @NotBlank
    private String question;

    public String getQuestion() {
        return question;
    }

    public void setQuestion(String question) {
        this.question = question;
    }
}
