package com.example.financerag.feedback;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public class FeedbackRequest {

    @NotNull
    private FeedbackRating rating;

    @Size(max = 1000)
    private String comment;

    public FeedbackRating getRating() {
        return rating;
    }

    public void setRating(FeedbackRating rating) {
        this.rating = rating;
    }

    public String getComment() {
        return comment;
    }

    public void setComment(String comment) {
        this.comment = comment;
    }
}
