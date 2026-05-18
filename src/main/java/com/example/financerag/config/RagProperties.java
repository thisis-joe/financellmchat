package com.example.financerag.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "rag.service")
public record RagProperties(String baseUrl) {
}
