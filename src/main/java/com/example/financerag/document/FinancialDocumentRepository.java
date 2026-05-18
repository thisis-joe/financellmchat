package com.example.financerag.document;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface FinancialDocumentRepository extends JpaRepository<FinancialDocument, Long> {

    List<FinancialDocument> findTop5ByTitleContainingIgnoreCaseOrContentContainingIgnoreCaseOrderByCreatedAtDesc(
            String titleKeyword,
            String contentKeyword
    );
}
