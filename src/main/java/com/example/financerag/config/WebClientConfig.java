package com.example.financerag.config;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

@Configuration
@EnableConfigurationProperties(RagProperties.class)
public class WebClientConfig {

    @Bean
    RestClient ragRestClient(RagProperties properties) {
        return RestClient.builder()
                .baseUrl(properties.baseUrl())
                .requestFactory(new SimpleClientHttpRequestFactory())
                .build();
    }
}
