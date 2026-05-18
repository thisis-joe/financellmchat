package com.example.financerag.query;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface QueryHistoryRepository extends JpaRepository<QueryHistory, Long> {

    List<QueryHistory> findTop10ByOrderByCreatedAtDesc();
}
