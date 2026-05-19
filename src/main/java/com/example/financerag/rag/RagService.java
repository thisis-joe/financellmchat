package com.example.financerag.rag;

import com.example.financerag.common.ResourceNotFoundException;
import com.example.financerag.query.QueryHistory;
import com.example.financerag.query.QueryHistoryRepository;
import com.example.financerag.query.QueryHistoryResponse;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.stream.IntStream;

@Service
public class RagService {

    private static final Logger log = LoggerFactory.getLogger(RagService.class);
    private static final TypeReference<List<RagAnswerResponse.Citation>> CITATION_LIST_TYPE = new TypeReference<>() {
    };

    private final RagClient ragClient;
    private final QueryHistoryRepository historyRepository;
    private final ObjectMapper objectMapper;

    public RagService(RagClient ragClient, QueryHistoryRepository historyRepository, ObjectMapper objectMapper) {
        this.ragClient = ragClient;
        this.historyRepository = historyRepository;
        this.objectMapper = objectMapper;
    }

    @Transactional
    public RagAnswerResponse ask(RagQuestionRequest request) {
        String question = request.getQuestion();
        RagAnswerResponse response = ragClient.ask(request);
        QueryHistory history = historyRepository.save(new QueryHistory(
                question,
                response.answer(),
                toJson(response.citations()),
                response.status()
        ));
        logAnswerEvidence(history, response.citations());
        return response.withHistoryId(history.getId());
    }

    @Transactional(readOnly = true)
    public List<QueryHistoryResponse> recentHistories() {
        return historyRepository.findTop10ByOrderByCreatedAtDesc()
                .stream()
                .map(QueryHistoryResponse::from)
                .toList();
    }

    @Transactional(readOnly = true)
    public RagEvidenceResponse evidence(Long historyId) {
        QueryHistory history = historyRepository.findById(historyId)
                .orElseThrow(() -> new ResourceNotFoundException("질문 이력을 찾을 수 없습니다. historyId=" + historyId));
        List<RagAnswerResponse.Citation> citations = parseCitations(history.getCitationsJson());
        List<RagEvidenceResponse.Evidence> evidences = IntStream.range(0, citations.size())
                .mapToObj(index -> toEvidence(index + 1, citations.get(index)))
                .toList();
        return new RagEvidenceResponse(
                history.getId(),
                history.getQuestion(),
                history.getStatus(),
                buildEvidenceSummary(history.getStatus(), evidences.size()),
                evidences,
                history.getCreatedAt()
        );
    }

    private String toJson(List<RagAnswerResponse.Citation> citations) {
        if (citations == null) {
            return "[]";
        }
        try {
            return objectMapper.writeValueAsString(citations);
        } catch (JsonProcessingException e) {
            return "[]";
        }
    }

    private List<RagAnswerResponse.Citation> parseCitations(String citationsJson) {
        if (citationsJson == null || citationsJson.isBlank()) {
            return List.of();
        }
        try {
            List<RagAnswerResponse.Citation> citations = objectMapper.readValue(citationsJson, CITATION_LIST_TYPE);
            return citations == null ? List.of() : citations;
        } catch (JsonProcessingException e) {
            log.warn("Failed to parse stored citations. reason={}", e.getMessage());
            return List.of();
        }
    }

    private RagEvidenceResponse.Evidence toEvidence(int rank, RagAnswerResponse.Citation citation) {
        return new RagEvidenceResponse.Evidence(
                rank,
                citation.documentId(),
                citation.title(),
                citation.category(),
                citation.institution(),
                citation.productName(),
                citation.productType(),
                citation.source(),
                citation.sourceUrl(),
                citation.score(),
                citation.snippet()
        );
    }

    private String buildEvidenceSummary(String status, int evidenceCount) {
        if (evidenceCount == 0) {
            if ("DIRECT".equals(status)) {
                return "직접 응답입니다. 문서 검색이 필요하지 않아 검색 근거 문서는 없습니다.";
            }
            return "저장된 검색 근거 문서가 없습니다.";
        }
        return "답변 생성에 사용한 검색 근거 문서 " + evidenceCount + "개입니다. 점수와 발췌문은 검색 순위를 이해하기 위한 디버그 정보입니다.";
    }

    private void logAnswerEvidence(QueryHistory history, List<RagAnswerResponse.Citation> citations) {
        if (citations == null || citations.isEmpty()) {
            log.info("RAG evidence historyId={} status={} citations=none", history.getId(), history.getStatus());
            return;
        }
        String evidence = citations.stream()
                .limit(4)
                .map(citation -> citation.title() + "(" + String.format("%.4f", citation.score()) + ")")
                .toList()
                .toString();
        log.info("RAG evidence historyId={} status={} citations={}", history.getId(), history.getStatus(), evidence);
    }
}
