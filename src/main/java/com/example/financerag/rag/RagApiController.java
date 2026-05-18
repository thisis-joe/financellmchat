package com.example.financerag.rag;

import com.example.financerag.query.QueryHistoryResponse;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api")
public class RagApiController {

    private final RagService ragService;

    public RagApiController(RagService ragService) {
        this.ragService = ragService;
    }

    @PostMapping("/ask")
    public RagAnswerResponse ask(@Valid @RequestBody RagQuestionRequest request) {
        return ragService.ask(request.getQuestion());
    }

    @GetMapping("/histories")
    public List<QueryHistoryResponse> histories() {
        return ragService.recentHistories();
    }
}
