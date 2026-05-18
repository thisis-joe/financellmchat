package com.example.financerag.rag;

import com.example.financerag.query.QueryHistory;
import com.example.financerag.query.QueryHistoryRepository;
import com.example.financerag.query.QueryHistoryResponse;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class RagService {

    private final RagClient ragClient;
    private final QueryHistoryRepository historyRepository;
    private final ObjectMapper objectMapper;

    public RagService(RagClient ragClient, QueryHistoryRepository historyRepository, ObjectMapper objectMapper) {
        this.ragClient = ragClient;
        this.historyRepository = historyRepository;
        this.objectMapper = objectMapper;
    }

    @Transactional
    public RagAnswerResponse ask(String question) {
        RagAnswerResponse response = ragClient.ask(question);
        QueryHistory history = historyRepository.save(new QueryHistory(
                question,
                response.answer(),
                toJson(response.citations()),
                response.status()
        ));
        return response.withHistoryId(history.getId());
    }

    @Transactional(readOnly = true)
    public List<QueryHistoryResponse> recentHistories() {
        return historyRepository.findTop10ByOrderByCreatedAtDesc()
                .stream()
                .map(QueryHistoryResponse::from)
                .toList();
    }

    private String toJson(List<RagAnswerResponse.Citation> citations) {
        try {
            return objectMapper.writeValueAsString(citations);
        } catch (JsonProcessingException e) {
            return "[]";
        }
    }
}
