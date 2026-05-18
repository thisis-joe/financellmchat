package com.example.financerag.common;

import java.time.LocalDateTime;

public record ApiErrorResponse(
        String message,
        int status,
        LocalDateTime timestamp
) {

    public static ApiErrorResponse of(String message, int status) {
        return new ApiErrorResponse(message, status, LocalDateTime.now());
    }
}
