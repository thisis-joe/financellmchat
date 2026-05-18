package com.example.financerag.document;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;

import java.time.LocalDate;
import java.time.LocalDateTime;

@Entity
@Table(name = "financial_documents")
public class FinancialDocument {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 200)
    private String title;

    @Column(nullable = false, length = 80)
    private String category;

    @Column(length = 80)
    private String institution;

    @Column(length = 160)
    private String productName;

    @Column(length = 80)
    private String productType;

    @Column(nullable = false, length = 120)
    private String source;

    @Column(length = 500)
    private String sourceUrl;

    private LocalDate publishedDate;

    @Column(nullable = false, columnDefinition = "TEXT")
    private String content;

    @Column(nullable = false)
    private LocalDateTime createdAt;

    protected FinancialDocument() {
    }

    @PrePersist
    void prePersist() {
        this.createdAt = LocalDateTime.now();
    }

    public Long getId() {
        return id;
    }

    public String getTitle() {
        return title;
    }

    public String getCategory() {
        return category;
    }

    public String getInstitution() {
        return institution;
    }

    public String getProductName() {
        return productName;
    }

    public String getProductType() {
        return productType;
    }

    public String getSource() {
        return source;
    }

    public String getSourceUrl() {
        return sourceUrl;
    }

    public LocalDate getPublishedDate() {
        return publishedDate;
    }

    public String getContent() {
        return content;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }
}
