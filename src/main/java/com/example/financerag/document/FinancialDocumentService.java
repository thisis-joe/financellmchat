package com.example.financerag.document;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Locale;

@Service
@Transactional(readOnly = true)
public class FinancialDocumentService {

    private final FinancialDocumentRepository repository;

    public FinancialDocumentService(FinancialDocumentRepository repository) {
        this.repository = repository;
    }

    public List<FinancialDocument> searchFallback(String question) {
        List<FinancialDocument> exactMatches = repository
                .findTop5ByTitleContainingIgnoreCaseOrContentContainingIgnoreCaseOrderByCreatedAtDesc(question, question);
        if (!exactMatches.isEmpty()) {
            return exactMatches;
        }

        List<String> keywords = List.of(question.split("\\s+"))
                .stream()
                .map(keyword -> keyword.replaceAll("[^가-힣a-zA-Z0-9]", ""))
                .filter(keyword -> keyword.length() >= 2)
                .map(keyword -> keyword.toLowerCase(Locale.ROOT))
                .toList();

        return repository.findAll()
                .stream()
                .filter(document -> containsAnyKeyword(document, keywords))
                .limit(5)
                .toList();
    }

    private boolean containsAnyKeyword(FinancialDocument document, List<String> keywords) {
        String searchableText = (document.getTitle() + " " + document.getContent()).toLowerCase(Locale.ROOT);
        return keywords.stream().anyMatch(searchableText::contains);
    }
}
