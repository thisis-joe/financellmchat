package com.example.financerag.rag;

import com.example.financerag.document.FinancialDocument;
import com.example.financerag.document.FinancialDocumentService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.util.List;

@Component
public class RagClient {

    private static final Logger log = LoggerFactory.getLogger(RagClient.class);

    private final RestClient restClient;
    private final FinancialDocumentService documentService;
    private final ObjectMapper objectMapper;

    public RagClient(RestClient ragRestClient, FinancialDocumentService documentService, ObjectMapper objectMapper) {
        this.restClient = ragRestClient;
        this.documentService = documentService;
        this.objectMapper = objectMapper;
    }

    public RagAnswerResponse ask(String question) {
        try {
            RagAnswerResponse response = restClient.post()
                    .uri("/ask")
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(toJson(question))
                    .retrieve()
                    .body(RagAnswerResponse.class);

            if (response != null) {
                return response;
            }
        } catch (RuntimeException e) {
            // 1차 버전은 Python RAG 서비스가 꺼져 있어도 Spring MVC 학습 흐름을 확인할 수 있게 둔다.
            log.warn("Python RAG service call failed. fallback search will be used. reason={}", e.getMessage());
        }

        return fallback(question);
    }

    private String toJson(String question) {
        try {
            return objectMapper.writeValueAsString(new RagApiRequest(question));
        } catch (JsonProcessingException e) {
            throw new IllegalArgumentException("질문을 JSON으로 변환할 수 없습니다.", e);
        }
    }

    private RagAnswerResponse fallback(String question) {
        List<RagAnswerResponse.Citation> citations = documentService.searchFallback(question)
                .stream()
                .map(this::toCitation)
                .toList();

        String answer = citations.isEmpty()
                ? "Python RAG 서비스에 연결하지 못했고, Spring fallback 검색에서도 관련 문서를 찾지 못했습니다."
                : "Python RAG 서비스에 연결하지 못해 Spring fallback 검색 결과를 반환합니다. 아래 근거 문서를 확인해 주세요.";

        return new RagAnswerResponse(null, question, answer, citations, "FALLBACK");
    }

    private RagAnswerResponse.Citation toCitation(FinancialDocument document) {
        String content = document.getContent();
        String snippet = content.length() > 180 ? content.substring(0, 180) + "..." : content;
        return new RagAnswerResponse.Citation(
                document.getId(),
                document.getTitle(),
                document.getCategory(),
                document.getInstitution(),
                document.getProductName(),
                document.getProductType(),
                document.getSource(),
                document.getSourceUrl(),
                0.0,
                snippet
        );
    }
}
