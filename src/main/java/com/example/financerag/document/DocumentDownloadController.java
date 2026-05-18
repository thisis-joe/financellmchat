package com.example.financerag.document;

import org.springframework.core.io.Resource;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/documents")
public class DocumentDownloadController {

    private final DocumentDownloadService downloadService;

    public DocumentDownloadController(DocumentDownloadService downloadService) {
        this.downloadService = downloadService;
    }

    @GetMapping("/{documentId}/download")
    public ResponseEntity<Resource> download(@PathVariable Long documentId) {
        return downloadService.download(documentId);
    }
}
